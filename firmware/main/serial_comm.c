#include "serial_comm.h"
#include "driver/uart.h"
#include <stdio.h>
#include <string.h>
#include <esp_log.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

#ifndef CONFIG_ALERT_UART_TX_GPIO
#define UART_TX_PIN 17
#else
#define UART_TX_PIN CONFIG_ALERT_UART_TX_GPIO
#endif

#ifndef CONFIG_ALERT_UART_RX_GPIO
#define UART_RX_PIN 18
#else
#define UART_RX_PIN CONFIG_ALERT_UART_RX_GPIO
#endif

#ifndef CONFIG_ALERT_UART_BAUD_RATE
#define UART_BAUD 115200
#else
#define UART_BAUD CONFIG_ALERT_UART_BAUD_RATE
#endif

#define BUF_SIZE        1024
#define PACKET_BUF_SIZE 256

static const char *TAG = "SERIAL_COMM";
static bool driver_installed = false;

#if ALERT_TRANSPORT_IS_CONSOLE
/* ------------------------------------------------------------------ */
/* Console transport: stdout / stdin (same USB port used for flashing) */
/* ------------------------------------------------------------------ */
#include <stdlib.h>

void serial_comm_init(void) {
    if (driver_installed) {
        return;
    }
    /* Unbuffered stdin so single bytes typed by the dashboard are seen at once. */
    setvbuf(stdin, NULL, _IONBF, 0);
    driver_installed = true;
    ESP_LOGI(TAG, "Alert channel = console (stdout/stdin). Use the board's USB port.");
}

bool serial_comm_is_ready(void) {
    return driver_installed;
}

int serial_comm_read(uint8_t *buf, size_t max_len, uint32_t timeout_ms) {
    if (!buf || max_len == 0 || !driver_installed) {
        vTaskDelay(pdMS_TO_TICKS(timeout_ms ? timeout_ms : 10));
        return 0;
    }
    size_t n = 0;
    const TickType_t start = xTaskGetTickCount();
    const TickType_t limit = pdMS_TO_TICKS(timeout_ms);

    while (n < max_len) {
        int c = getchar();
        if (c == EOF) {
            clearerr(stdin);
            if (n > 0 || (xTaskGetTickCount() - start) >= limit) {
                break;
            }
            vTaskDelay(pdMS_TO_TICKS(10));
            continue;
        }
        buf[n++] = (uint8_t)c;
        if (c == '\n') {
            break;
        }
    }
    return (int)n;
}

static bool write_packet(const char *packet, int len) {
    if (len <= 0 || len >= PACKET_BUF_SIZE || !driver_installed) {
        return false;
    }
    /* Leading '\n' guarantees the frame starts on its own line even if an
     * ESP_LOG line was interrupted just before it. */
    int written = printf("\n%s", packet);
    fflush(stdout);
    return written > 0;
}

#else
/* ------------------------------------------------------------------ */
/* Dedicated-UART transport                                            */
/* ------------------------------------------------------------------ */

void serial_comm_init(void) {
    if (driver_installed) {
        return;
    }

    const uart_config_t uart_config = {
        .baud_rate = UART_BAUD,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };

    esp_err_t err = uart_driver_install(ALERT_UART_PORT, BUF_SIZE * 2, BUF_SIZE * 2, 0, NULL, 0);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to install UART driver on port %d (0x%x)", ALERT_UART_PORT, err);
        return;
    }

    err = uart_param_config(ALERT_UART_PORT, &uart_config);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to configure UART port %d (0x%x)", ALERT_UART_PORT, err);
        return;
    }

    err = uart_set_pin(ALERT_UART_PORT, UART_TX_PIN, UART_RX_PIN, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to assign UART pins (0x%x)", err);
        return;
    }

    driver_installed = true;
    ESP_LOGI(TAG, "Alert UART Initialized on Port %d (TX:%d, RX:%d, Baud:%d)",
             ALERT_UART_PORT, UART_TX_PIN, UART_RX_PIN, UART_BAUD);
}

bool serial_comm_is_ready(void) {
    return driver_installed;
}

int serial_comm_read(uint8_t *buf, size_t max_len, uint32_t timeout_ms) {
    if (!buf || max_len == 0 || !driver_installed) {
        vTaskDelay(pdMS_TO_TICKS(timeout_ms ? timeout_ms : 10));
        return 0;
    }
    int len = uart_read_bytes(ALERT_UART_PORT, buf, max_len, pdMS_TO_TICKS(timeout_ms));
    return len > 0 ? len : 0;
}

static bool write_packet(const char *packet, int len) {
    if (len <= 0 || len >= PACKET_BUF_SIZE || !driver_installed) {
        return false;
    }
    int written = uart_write_bytes(ALERT_UART_PORT, packet, len);
    return written == len;
}
#endif /* ALERT_TRANSPORT_IS_CONSOLE */

/* ------------------------------------------------------------------ */
/* Frame builders (identical for both transports)                      */
/* ------------------------------------------------------------------ */

bool serial_comm_send_alert(const char *level, const char *event_code) {
    if (!level || !event_code) return false;
    char packet[PACKET_BUF_SIZE];
    int len = snprintf(packet, sizeof(packet), "::ALERT:%s:%s::\n", level, event_code);
    return write_packet(packet, len);
}

bool serial_comm_send_alert_with_hash(const char *level, const char *event_code,
                                     const char *orig_hash, const char *curr_hash) {
    if (!level || !event_code) return false;
    char packet[PACKET_BUF_SIZE];
    int len = snprintf(packet, sizeof(packet),
                       "::ALERT:%s:%s|ORIG:%s|CURR:%s::\n",
                       level, event_code,
                       orig_hash ? orig_hash : "N/A",
                       curr_hash ? curr_hash : "N/A");
    return write_packet(packet, len);
}

bool serial_comm_send_status(const char *fw_version, const char *hardware_revision) {
    if (!fw_version || !hardware_revision) return false;
    char packet[PACKET_BUF_SIZE];
    int len = snprintf(packet, sizeof(packet), "::STATUS:%s:%s::\n", fw_version, hardware_revision);
    return write_packet(packet, len);
}

bool serial_comm_send_rehash(const char *status, const char *hash_val) {
    if (!status) return false;
    char packet[PACKET_BUF_SIZE];
    int len = snprintf(packet, sizeof(packet), "::REHASH:%s:%s::\n", status, hash_val ? hash_val : "");
    return write_packet(packet, len);
}

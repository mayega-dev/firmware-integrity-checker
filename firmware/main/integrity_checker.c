#include "integrity_checker.h"
#include "crypto.h"
#include "logger.h"
#include "rollback.h"
#include "serial_comm.h"
#include "firmware_config.h"
#include "driver/uart.h"
#include <esp_log.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <string.h>
#include <stdio.h>

static const char *TAG = "INTEGRITY_MONITOR";
static uint8_t golden_baseline_hash[HASH_SIZE_BYTES];
static bool is_baseline_set = false;
static bool baseline_is_trusted_reference = false;

#if ENABLE_TAMPER_SIMULATION
static bool simulate_tamper_attack = false;
#endif

#define RX_BUF_SIZE 128

static void handle_verification_failure(void) {
    logger_log_event("INTEGRITY_FAIL", "Memory mismatch in app partition");

#if SECURITY_PANIC_REACTION == 2
    ESP_LOGE(TAG, "Security panic reaction: triggering software reset.");
    vTaskDelay(pdMS_TO_TICKS(200));
    esp_restart();
#else
    ESP_LOGE(TAG, "Security panic reaction: halting further automated verification.");
#endif
}

static char fw_ver_str[32];

/* Re-baseline to whatever is running right now (RAM only - the NVS golden
 * hash, if one was provisioned, is deliberately left untouched). */
static void recalibrate_baseline(void) {
    uint8_t current_hash[HASH_SIZE_BYTES];
    if (crypto_calculate_partition_hash(MONITORED_PARTITION_LABEL, current_hash) != ESP_OK) {
        serial_comm_send_alert("WARNING", "RECALIBRATE_FAILED");
        return;
    }
    memcpy(golden_baseline_hash, current_hash, HASH_SIZE_BYTES);
    is_baseline_set = true;
    baseline_is_trusted_reference = false;

    char hex[HASH_HEX_STR_LEN];
    crypto_hash_to_str(golden_baseline_hash, hex, sizeof(hex));
    ESP_LOGW(TAG, "Baseline re-calibrated by dashboard command: %s", hex);
    logger_log_event("BASELINE_RECAL", "Baseline re-calibrated via UART");
    serial_comm_send_rehash("PASS", hex);
    serial_comm_send_alert_with_hash("WARNING", "SYSTEM_RESTORED", hex, hex);
}

static void integrity_checker_task(void *pvParameters) {
    ESP_LOGI(TAG, "Runtime Integrity Monitor Started.");

    // Guarantee serial comms are initialized
    serial_comm_init();

    snprintf(fw_ver_str, sizeof(fw_ver_str), "%d.%d.%d",
             FIRMWARE_VERSION_MAJOR, FIRMWARE_VERSION_MINOR, FIRMWARE_VERSION_PATCH);

    // Emit initial status frame so dashboard populates FIRMWARE VERSION tile
    serial_comm_send_status(fw_ver_str, HARDWARE_REVISION);

    if (crypto_load_reference_hash(golden_baseline_hash)) {
        is_baseline_set = true;
        baseline_is_trusted_reference = true;
        ESP_LOGI(TAG, "Golden reference hash loaded from provisioned NVS store.");
    } else if (crypto_calculate_partition_hash(MONITORED_PARTITION_LABEL, golden_baseline_hash) == ESP_OK) {
        is_baseline_set = true;
        baseline_is_trusted_reference = false;
        ESP_LOGW(TAG, "No provisioned reference hash found - falling back to runtime baseline.");
    } else {
        ESP_LOGE(TAG, "Failed to establish integrity reference hash!");
    }

    if (is_baseline_set) {
        if (baseline_is_trusted_reference) {
            rollback_commit_version(FIRMWARE_VERSION_MAJOR);
        }

        // Emit baseline rehash frame immediately on boot so UI updates Baseline Threshold
        char baseline_hex[HASH_HEX_STR_LEN];
        crypto_hash_to_str(golden_baseline_hash, baseline_hex, sizeof(baseline_hex));
        serial_comm_send_rehash("PASS", baseline_hex);
        serial_comm_send_alert("INFO", "STATUS_SAFE");
    }

    uint8_t rx_data[RX_BUF_SIZE];
    TickType_t last_check = xTaskGetTickCount();

    while (1) {
        // Blocks up to 100 ms (UART) or polls stdin for up to 100 ms (console).
        int len = serial_comm_read(rx_data, RX_BUF_SIZE - 1, 100);

        if (len > 0) {
            rx_data[len] = '\0';
            char *msg = (char *)rx_data;

            if (strstr(msg, "::RECALIBRATE_BASELINE::") != NULL) {
                ESP_LOGI(TAG, "Re-calibrate requested by dashboard.");
                serial_comm_send_status(fw_ver_str, HARDWARE_REVISION);
                recalibrate_baseline();
            } else if (strstr(msg, "::POLL::") != NULL ||
                       strstr(msg, "::REHASH::") != NULL ||
                       strstr(msg, "::RESET_FIRMWARE::") != NULL) {
                // RESET_FIRMWARE cannot restore an image from here; the safest
                // useful reply is a fresh status + verification sweep so the
                // dashboard re-establishes its view of the device.
                ESP_LOGI(TAG, "Verification check requested by dashboard engine.");
                serial_comm_send_status(fw_ver_str, HARDWARE_REVISION);
                integrity_checker_verify_now();
                last_check = xTaskGetTickCount();
            }
#if ENABLE_TAMPER_SIMULATION
            else if (strstr(msg, "::TAMPER::") != NULL) {
                ESP_LOGW(TAG, "DEBUG BUILD: Injecting a simulated runtime tamper attack command!");
                simulate_tamper_attack = true;
                integrity_checker_verify_now();
                last_check = xTaskGetTickCount();
            }
#endif
        }

        if ((xTaskGetTickCount() - last_check) >= pdMS_TO_TICKS(RUNTIME_CHECK_INTERVAL_MS)) {
            last_check = xTaskGetTickCount();
            if (is_baseline_set
#if ENABLE_TAMPER_SIMULATION
                && !simulate_tamper_attack
#endif
            ) {
                // Re-send STATUS every cycle: the boot-time frame is usually
                // emitted before the dashboard has opened the port.
                serial_comm_send_status(fw_ver_str, HARDWARE_REVISION);
                integrity_checker_verify_now();
            }
        }
    }
}

bool integrity_checker_verify_now(void) {
    if (!is_baseline_set) {
        return false;
    }

    uint8_t current_hash[HASH_SIZE_BYTES];

    if (crypto_calculate_partition_hash(MONITORED_PARTITION_LABEL, current_hash) == ESP_OK) {
#if ENABLE_TAMPER_SIMULATION
        if (simulate_tamper_attack) {
            current_hash[0] ^= 0xFF;
            simulate_tamper_attack = false;
        }
#endif

        char orig_hash_hex[HASH_HEX_STR_LEN];
        char curr_hash_hex[HASH_HEX_STR_LEN];
        crypto_hash_to_str(golden_baseline_hash, orig_hash_hex, sizeof(orig_hash_hex));
        crypto_hash_to_str(current_hash, curr_hash_hex, sizeof(curr_hash_hex));

        if (memcmp(golden_baseline_hash, current_hash, HASH_SIZE_BYTES) != 0) {
            ESP_LOGE(TAG, "CRITICAL: Firmware Integrity Violation Detected!");
            serial_comm_send_rehash("FAIL", curr_hash_hex);
            serial_comm_send_alert_with_hash("CRITICAL", "FIRMWARE_TAMPERED", orig_hash_hex, curr_hash_hex);
            handle_verification_failure();
            return false;
        } else {
            ESP_LOGI(TAG, "Runtime integrity verified: OK. Hash: %s", curr_hash_hex);
            serial_comm_send_rehash("PASS", curr_hash_hex);
            serial_comm_send_alert("INFO", "STATUS_SAFE");
            return true;
        }
    }
    return false;
}

void integrity_checker_init(void) {
    serial_comm_init();
    BaseType_t ret = xTaskCreate(integrity_checker_task, "integrity_task", 6144, NULL, 5, NULL);
    if (ret != pdPASS) {
        ESP_LOGE(TAG, "Failed to create integrity_checker_task (0x%x)", ret);
    }
}
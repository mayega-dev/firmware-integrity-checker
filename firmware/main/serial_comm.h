#ifndef SERIAL_COMM_H
#define SERIAL_COMM_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "driver/uart.h"
#include "sdkconfig.h"

/*
 * Transport selection (menuconfig -> Firmware Integrity Checker):
 *   CONFIG_ALERT_TRANSPORT_CONSOLE (default): frames go through stdout/stdin,
 *       i.e. the board's normal USB/console port. One cable, nothing to wire.
 *   CONFIG_ALERT_TRANSPORT_UART: frames go through a dedicated UART on
 *       CONFIG_ALERT_UART_TX_GPIO / RX_GPIO (needs a USB-TTL adapter).
 * If neither symbol exists (old sdkconfig) we default to the console.
 */
#if !defined(CONFIG_ALERT_TRANSPORT_UART)
#define ALERT_TRANSPORT_IS_CONSOLE 1
#else
#define ALERT_TRANSPORT_IS_CONSOLE 0
#endif

#ifndef CONFIG_ALERT_UART_PORT_NUM
#define ALERT_UART_PORT UART_NUM_1
#else
#define ALERT_UART_PORT ((uart_port_t)CONFIG_ALERT_UART_PORT_NUM)
#endif

void serial_comm_init(void);
bool serial_comm_is_ready(void);

/**
 * @brief Read incoming command bytes from the dashboard.
 * @return number of bytes placed in buf (0 if nothing arrived within timeout_ms)
 */
int serial_comm_read(uint8_t *buf, size_t max_len, uint32_t timeout_ms);

bool serial_comm_send_alert(const char *level, const char *event_code);
bool serial_comm_send_alert_with_hash(const char *level, const char *event_code,
                                     const char *orig_hash, const char *curr_hash);
bool serial_comm_send_status(const char *fw_version, const char *hardware_revision);
bool serial_comm_send_rehash(const char *status, const char *hash_val);

#endif // SERIAL_COMM_H

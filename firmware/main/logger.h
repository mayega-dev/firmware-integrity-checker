#ifndef LOGGER_H
#define LOGGER_H

#include <stdint.h>
#include <stdbool.h>

/**
 * @brief Logs local events to NVS (Non-Volatile Storage) as a wear-aware
 *        ring buffer, bounded by SECURE_LOG_MAX_ENTRIES.
 */
void logger_init(void);

/**
 * @brief Records a security event. Persists to NVS (in addition to live ESP_LOG console output)
 *        so the entry survives reboot.
 */
void logger_log_event(const char *event_type, const char *message);

/**
 * @brief Returns the number of log entries currently stored.
 */
uint32_t logger_get_entry_count(void);

/**
 * @brief Fetches a stored log entry by its logical index (0 = oldest entry).
 * @param index Logical log index.
 * @param out_type Output buffer for event type (at least 16 bytes).
 * @param out_message Output buffer for message (at least LOG_ENTRY_MSG_MAX_LEN bytes).
 * @return true on success, false otherwise.
 */
bool logger_get_entry(uint32_t index, char *out_type, char *out_message);

#endif // LOGGER_H
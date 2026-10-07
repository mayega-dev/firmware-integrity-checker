#include "logger.h"
#include "firmware_config.h"
#include <esp_log.h>
#include <nvs_flash.h>
#include <nvs.h>
#include <string.h>
#include <stdio.h>
#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>

static const char *TAG = "LOCAL_LOGGER";

typedef struct {
    char event_type[16];
    char message[LOG_ENTRY_MSG_MAX_LEN];
} log_entry_t;

static uint32_t log_head = 0;
static uint32_t log_count = 0;
static bool nvs_ready = false;
static SemaphoreHandle_t log_mutex = NULL;

void logger_init(void) {
    if (log_mutex == NULL) {
        log_mutex = xSemaphoreCreateMutex();
    }

    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    ESP_ERROR_CHECK(err);

    nvs_handle_t handle;
    err = nvs_open(LOG_NVS_NAMESPACE, NVS_READWRITE, &handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to open log NVS namespace (0x%x); logging will be RAM/console-only", err);
        nvs_ready = false;
        return;
    }

    int32_t stored_head = 0, stored_count = 0;
    if (nvs_get_i32(handle, LOG_NVS_KEY_HEAD, &stored_head) == ESP_OK) {
        log_head = (uint32_t)stored_head;
    }
    if (nvs_get_i32(handle, LOG_NVS_KEY_COUNT, &stored_count) == ESP_OK) {
        log_count = (uint32_t)stored_count;
    }
    nvs_close(handle);
    nvs_ready = true;

    ESP_LOGI(TAG, "Secure Event Logger Partition Initialized (%lu/%d entries retained).",
             (unsigned long)log_count, SECURE_LOG_MAX_ENTRIES);
}

void logger_log_event(const char *event_type, const char *message) {
    if (!event_type || !message) {
        ESP_LOGE(TAG, "Invalid NULL parameters passed to logger_log_event");
        return;
    }

    // Always surface to the live console regardless of NVS availability.
    ESP_LOGW(TAG, "[SECURE LOG] Type: %s | Msg: %s", event_type, message);

    if (!nvs_ready) {
        return;
    }

    if (log_mutex && xSemaphoreTake(log_mutex, pdMS_TO_TICKS(1000)) != pdTRUE) {
        ESP_LOGE(TAG, "Timeout acquiring logger mutex");
        return;
    }

    nvs_handle_t handle;
    esp_err_t err = nvs_open(LOG_NVS_NAMESPACE, NVS_READWRITE, &handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to open log NVS namespace for write (0x%x)", err);
        if (log_mutex) xSemaphoreGive(log_mutex);
        return;
    }

    log_entry_t entry = {0};
    strncpy(entry.event_type, event_type, sizeof(entry.event_type) - 1);
    strncpy(entry.message, message, sizeof(entry.message) - 1);

    char key[16];
    snprintf(key, sizeof(key), "e%04lu", (unsigned long)(log_head % SECURE_LOG_MAX_ENTRIES));

    err = nvs_set_blob(handle, key, &entry, sizeof(entry));
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to persist log entry '%s' (0x%x)", key, err);
        nvs_close(handle);
        if (log_mutex) xSemaphoreGive(log_mutex);
        return;
    }

    log_head = (log_head + 1) % SECURE_LOG_MAX_ENTRIES;
    if (log_count < SECURE_LOG_MAX_ENTRIES) {
        log_count++;
    }

    nvs_set_i32(handle, LOG_NVS_KEY_HEAD, (int32_t)log_head);
    nvs_set_i32(handle, LOG_NVS_KEY_COUNT, (int32_t)log_count);
    nvs_commit(handle);
    nvs_close(handle);

    if (log_mutex) xSemaphoreGive(log_mutex);
}

uint32_t logger_get_entry_count(void) {
    return log_count;
}

bool logger_get_entry(uint32_t index, char *out_type, char *out_message) {
    if (!nvs_ready || !out_type || !out_message) {
        return false;
    }

    if (log_mutex && xSemaphoreTake(log_mutex, pdMS_TO_TICKS(1000)) != pdTRUE) {
        return false;
    }

    if (index >= log_count) {
        if (log_mutex) xSemaphoreGive(log_mutex);
        return false;
    }

    uint32_t oldest_slot = (log_head + SECURE_LOG_MAX_ENTRIES - log_count) % SECURE_LOG_MAX_ENTRIES;
    uint32_t slot = (oldest_slot + index) % SECURE_LOG_MAX_ENTRIES;

    nvs_handle_t handle;
    esp_err_t err = nvs_open(LOG_NVS_NAMESPACE, NVS_READONLY, &handle);
    if (err != ESP_OK) {
        if (log_mutex) xSemaphoreGive(log_mutex);
        return false;
    }

    char key[16];
    snprintf(key, sizeof(key), "e%04lu", (unsigned long)slot);

    log_entry_t entry;
    size_t entry_size = sizeof(entry);
    err = nvs_get_blob(handle, key, &entry, &entry_size);
    nvs_close(handle);

    if (err != ESP_OK) {
        if (log_mutex) xSemaphoreGive(log_mutex);
        return false;
    }

    memcpy(out_type, entry.event_type, sizeof(entry.event_type));
    out_type[sizeof(entry.event_type) - 1] = '\0';

    memcpy(out_message, entry.message, sizeof(entry.message));
    out_message[sizeof(entry.message) - 1] = '\0';

    if (log_mutex) xSemaphoreGive(log_mutex);
    return true;
}
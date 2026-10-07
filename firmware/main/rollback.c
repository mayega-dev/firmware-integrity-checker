#include "rollback.h"
#include "firmware_config.h"
#include <esp_log.h>
#include <nvs.h>

static const char *TAG = "ROLLBACK_PROT";

// Cached in RAM after init so hot-path checks don't hit NVS every time.
static int min_allowed_version = ROLLBACK_BASELINE_VERSION;

void rollback_init(void) {
    nvs_handle_t handle;
    esp_err_t err = nvs_open(ROLLBACK_NVS_NAMESPACE, NVS_READWRITE, &handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to open rollback NVS namespace (0x%x); falling back to baseline %d",
                 err, ROLLBACK_BASELINE_VERSION);
        min_allowed_version = ROLLBACK_BASELINE_VERSION;
        return;
    }

    int32_t stored_version = 0;
    err = nvs_get_i32(handle, ROLLBACK_NVS_KEY_MIN_VER, &stored_version);
    if (err == ESP_ERR_NVS_NOT_FOUND) {
        // First-ever boot: seed counter so it cannot be reset by re-flashing an old NVS image.
        stored_version = ROLLBACK_BASELINE_VERSION;
        esp_err_t set_err = nvs_set_i32(handle, ROLLBACK_NVS_KEY_MIN_VER, stored_version);
        if (set_err == ESP_OK) {
            set_err = nvs_commit(handle);
            if (set_err != ESP_OK) {
                ESP_LOGE(TAG, "Failed to commit seeded anti-rollback counter (0x%x)", set_err);
            }
        } else {
            ESP_LOGE(TAG, "Failed to seed anti-rollback counter (0x%x)", set_err);
        }
        ESP_LOGI(TAG, "Anti-Rollback counter seeded at baseline version %d", (int)stored_version);
    } else if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to read anti-rollback counter (0x%x); using baseline %d", err,
                 ROLLBACK_BASELINE_VERSION);
        stored_version = ROLLBACK_BASELINE_VERSION;
    }

    // Enforce baseline lower floor strictly
    if (stored_version < ROLLBACK_BASELINE_VERSION) {
        ESP_LOGW(TAG, "Stored version %d is below baseline %d; resetting floor to baseline",
                 (int)stored_version, ROLLBACK_BASELINE_VERSION);
        stored_version = ROLLBACK_BASELINE_VERSION;
    }

    min_allowed_version = (int)stored_version;
    nvs_close(handle);

    ESP_LOGI(TAG, "Anti-Rollback subsystem initialized. Minimum allowed version: %d", min_allowed_version);
}

bool rollback_check_version(int running_version) {
    if (running_version < min_allowed_version) {
        ESP_LOGE(TAG, "Violation: Detected firmware version %d. Minimum required is %d", running_version,
                 min_allowed_version);
        return false;
    }
    return true;
}

void rollback_commit_version(int running_version) {
    if (running_version <= min_allowed_version) {
        return;
    }

    nvs_handle_t handle;
    esp_err_t err = nvs_open(ROLLBACK_NVS_NAMESPACE, NVS_READWRITE, &handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to open rollback NVS namespace for commit (0x%x)", err);
        return;
    }

    err = nvs_set_i32(handle, ROLLBACK_NVS_KEY_MIN_VER, (int32_t)running_version);
    if (err == ESP_OK) {
        esp_err_t commit_err = nvs_commit(handle);
        if (commit_err == ESP_OK) {
            min_allowed_version = running_version;
            ESP_LOGI(TAG, "Anti-Rollback floor advanced to version %d", running_version);
        } else {
            ESP_LOGE(TAG, "Failed to commit new anti-rollback floor to flash (0x%x)", commit_err);
        }
    } else {
        ESP_LOGE(TAG, "Failed to set new anti-rollback floor key in NVS (0x%x)", err);
    }
    nvs_close(handle);
}
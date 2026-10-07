#include <stdio.h>
#include <nvs_flash.h>
#include <esp_log.h>
#include "integrity_checker.h"
#include "serial_comm.h"

static const char *TAG = "MAIN";

void app_main(void) {
    ESP_LOGI(TAG, "Initializing System Flash & Hardware...");

    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    serial_comm_init();
    integrity_checker_init();

    ESP_LOGI(TAG, "System Initialization Complete.");
}
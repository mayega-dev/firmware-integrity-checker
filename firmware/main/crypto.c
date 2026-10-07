#include "crypto.h"
#include "firmware_config.h"
#include "mbedtls/sha256.h"
#include <esp_flash.h>
#include <esp_log.h>
#include <esp_partition.h>
#include <esp_ota_ops.h>
#include <nvs.h>
#include <inttypes.h>
#include <stdlib.h>
#include <stdio.h>

static const char *TAG = "CRYPTO";

esp_err_t crypto_calculate_partition_hash(const char *partition_label, uint8_t *output_hash) {
    if (!output_hash) {
        return ESP_ERR_INVALID_ARG;
    }

    const esp_partition_t *partition = NULL;

    // 1. Try specified partition label
    if (partition_label != NULL) {
        partition = esp_partition_find_first(ESP_PARTITION_TYPE_APP, ESP_PARTITION_SUBTYPE_ANY, partition_label);
    }

    // 2. Fallback to currently running partition
    if (partition == NULL) {
        partition = esp_ota_get_running_partition();
    }

    // 3. Fallback to any app partition
    if (partition == NULL) {
        partition = esp_partition_find_first(ESP_PARTITION_TYPE_APP, ESP_PARTITION_SUBTYPE_ANY, NULL);
    }

    if (partition == NULL) {
        ESP_LOGE(TAG, "No valid app partition found for hashing!");
        return ESP_ERR_NOT_FOUND;
    }

    ESP_LOGI(TAG, "Hashing partition: '%s' (Address: 0x%08" PRIx32 ", Size: %" PRIu32 " bytes)",
             partition->label, partition->address, partition->size);

    size_t chunk_size = 4096;
    uint8_t *buffer = malloc(chunk_size);
    if (!buffer) {
        return ESP_ERR_NO_MEM;
    }

    mbedtls_sha256_context ctx;
    mbedtls_sha256_init(&ctx);
    mbedtls_sha256_starts(&ctx, 0);

    size_t offset = 0;
    size_t size_to_read = partition->size;
    esp_err_t err = ESP_OK;

    while (size_to_read > 0) {
        size_t read_len = (size_to_read > chunk_size) ? chunk_size : size_to_read;
        err = esp_partition_read(partition, offset, buffer, read_len);
        if (err != ESP_OK) {
            ESP_LOGE(TAG, "Flash read failed at offset 0x%x", (unsigned int)offset);
            break;
        }

        mbedtls_sha256_update(&ctx, buffer, read_len);
        offset += read_len;
        size_to_read -= read_len;
    }

    mbedtls_sha256_finish(&ctx, output_hash);
    mbedtls_sha256_free(&ctx);
    free(buffer);

    return err;
}

void crypto_hash_to_str(const uint8_t *hash, char *out_str, size_t out_str_size) {
    if (!hash || !out_str || out_str_size < HASH_HEX_STR_LEN) {
        if (out_str && out_str_size > 0) {
            out_str[0] = '\0';
        }
        return;
    }

    for (int i = 0; i < HASH_SIZE_BYTES; i++) {
        snprintf(&out_str[i * 2], out_str_size - (i * 2), "%02x", hash[i]);
    }
    out_str[HASH_SIZE_BYTES * 2] = '\0';
}

bool crypto_load_reference_hash(uint8_t *out_hash) {
    if (!out_hash) {
        return false;
    }

    nvs_handle_t handle;
    esp_err_t err = nvs_open(REFHASH_NVS_NAMESPACE, NVS_READONLY, &handle);
    if (err != ESP_OK) {
        return false;
    }

    size_t len = HASH_SIZE_BYTES;
    err = nvs_get_blob(handle, REFHASH_NVS_KEY, out_hash, &len);
    nvs_close(handle);

    return (err == ESP_OK && len == HASH_SIZE_BYTES);
}

esp_err_t crypto_store_reference_hash(const uint8_t *hash) {
    if (!hash) {
        return ESP_ERR_INVALID_ARG;
    }

    nvs_handle_t handle;
    esp_err_t err = nvs_open(REFHASH_NVS_NAMESPACE, NVS_READWRITE, &handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to open reference-hash NVS namespace (0x%x)", err);
        return err;
    }

    err = nvs_set_blob(handle, REFHASH_NVS_KEY, hash, HASH_SIZE_BYTES);
    if (err == ESP_OK) {
        err = nvs_commit(handle);
    }
    nvs_close(handle);
    return err;
}
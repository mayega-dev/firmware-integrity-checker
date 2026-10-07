#ifndef CRYPTO_H
#define CRYPTO_H

#include <esp_err.h>
#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

#define HASH_SIZE_BYTES 32 // SHA-256 outputs 32 bytes
#define HASH_HEX_STR_LEN ((HASH_SIZE_BYTES * 2) + 1)

/**
 * @brief Computes the SHA-256 hash of a specific memory partition.
 * @param partition_label Label of the partition to hash (e.g., "factory")
 * @param output_hash Buffer to store the calculated 32-byte hash
 * @return esp_err_t ESP_OK on success
 */
esp_err_t crypto_calculate_partition_hash(const char *partition_label, uint8_t *output_hash);

/**
 * @brief Utility function to convert a byte array hash to a hex string.
 * @param hash Input byte hash array (HASH_SIZE_BYTES long)
 * @param out_str Output buffer for null-terminated hex string
 * @param out_str_size Size of out_str buffer (must be at least HASH_HEX_STR_LEN)
 */
void crypto_hash_to_str(const uint8_t *hash, char *out_str, size_t out_str_size);

/**
 * @brief Reads the signed golden reference hash provisioned into NVS.
 * @param out_hash Buffer to store the retrieved reference hash
 * @return true if a valid reference hash was retrieved.
 */
bool crypto_load_reference_hash(uint8_t *out_hash);

/**
 * @brief Provisions or overwrites the golden reference hash in NVS.
 * @param hash Pointer to 32-byte reference hash
 * @return esp_err_t ESP_OK on success
 */
esp_err_t crypto_store_reference_hash(const uint8_t *hash);

#endif // CRYPTO_H
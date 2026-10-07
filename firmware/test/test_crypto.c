#include "unity.h"
#include "crypto.h"
#include <string.h>

// Known-answer test vectors (NIST FIPS 180-4 / standard SHA-256 test vectors).
// crypto_calculate_partition_hash() hashes a flash partition, not an
// arbitrary buffer, so these vectors exercise crypto_hash_to_str() directly
// against known digests - the part of crypto.c that has no hardware
// dependency and is fully testable in isolation.

TEST_CASE("crypto_hash_to_str produces correct lowercase hex for known SHA-256 digest", "[crypto]")
{
    // SHA-256("") = e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
    uint8_t empty_string_hash[HASH_SIZE_BYTES] = {
        0xe3, 0xb0, 0xc4, 0x42, 0x98, 0xfc, 0x1c, 0x14,
        0x9a, 0xfb, 0xf4, 0xc8, 0x99, 0x6f, 0xb9, 0x24,
        0x27, 0xae, 0x41, 0xe4, 0x64, 0x9b, 0x93, 0x4c,
        0xa4, 0x95, 0x99, 0x1b, 0x78, 0x52, 0xb8, 0x55,
    };
    char out_str[HASH_SIZE_BYTES * 2 + 1];

    crypto_hash_to_str(empty_string_hash, out_str);

    TEST_ASSERT_EQUAL_STRING(
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        out_str
    );
    // Vector verified against `python3 -c "import hashlib; print(hashlib.sha256(b'').hexdigest())"`
}

TEST_CASE("crypto_hash_to_str output length is always exactly 64 hex chars plus null terminator", "[crypto]")
{
    uint8_t arbitrary_hash[HASH_SIZE_BYTES];
    memset(arbitrary_hash, 0xAB, sizeof(arbitrary_hash));
    char out_str[HASH_SIZE_BYTES * 2 + 1];

    crypto_hash_to_str(arbitrary_hash, out_str);

    TEST_ASSERT_EQUAL_INT(64, strlen(out_str));
    TEST_ASSERT_EQUAL_CHAR('\0', out_str[64]);
}

TEST_CASE("crypto_hash_to_str all-zero hash produces all-zero hex string", "[crypto]")
{
    uint8_t zero_hash[HASH_SIZE_BYTES] = {0};
    char out_str[HASH_SIZE_BYTES * 2 + 1];

    crypto_hash_to_str(zero_hash, out_str);

    TEST_ASSERT_EQUAL_STRING(
        "0000000000000000000000000000000000000000000000000000000000000000",
        out_str
    );
}

TEST_CASE("crypto_calculate_partition_hash returns ESP_ERR_NOT_FOUND for a nonexistent partition label", "[crypto][requires_hardware]")
{
    uint8_t output_hash[HASH_SIZE_BYTES];
    esp_err_t err = crypto_calculate_partition_hash("this_label_does_not_exist", output_hash);
    TEST_ASSERT_EQUAL(ESP_ERR_NOT_FOUND, err);
}

TEST_CASE("crypto_calculate_partition_hash succeeds for the real factory partition", "[crypto][requires_hardware]")
{
    uint8_t output_hash[HASH_SIZE_BYTES];
    esp_err_t err = crypto_calculate_partition_hash("factory", output_hash);
    TEST_ASSERT_EQUAL(ESP_OK, err);

    // A real hash should not be all-zero (extremely unlikely for actual
    // firmware content, and would indicate the read loop never executed).
    uint8_t zero_hash[HASH_SIZE_BYTES] = {0};
    TEST_ASSERT_NOT_EQUAL(0, memcmp(output_hash, zero_hash, HASH_SIZE_BYTES));
}
#include "unity.h"
#include "logger.h"
#include "firmware_config.h"
#include "nvs_flash.h"
#include "nvs.h"
#include <string.h>
#include <stdio.h>

static void erase_log_namespace(void)
{
    nvs_handle_t handle;
    if (nvs_open(LOG_NVS_NAMESPACE, NVS_READWRITE, &handle) == ESP_OK) {
        nvs_erase_all(handle);
        nvs_commit(handle);
        nvs_close(handle);
    }
}

TEST_CASE("logger starts with zero entries on a clean namespace", "[logger][requires_hardware]")
{
    erase_log_namespace();
    logger_init();

    TEST_ASSERT_EQUAL_UINT32(0, logger_get_entry_count());
}

TEST_CASE("logger_log_event increments entry count up to capacity", "[logger][requires_hardware]")
{
    erase_log_namespace();
    logger_init();

    logger_log_event("BOOT", "event 1");
    logger_log_event("INTEGRITY", "event 2");
    logger_log_event("INTEGRITY", "event 3");

    TEST_ASSERT_EQUAL_UINT32(3, logger_get_entry_count());
}

TEST_CASE("logger_get_entry retrieves entries in chronological order", "[logger][requires_hardware]")
{
    erase_log_namespace();
    logger_init();

    logger_log_event("BOOT", "first");
    logger_log_event("INTEGRITY", "second");
    logger_log_event("INTEGRITY", "third");

    char type_buf[16];
    char msg_buf[LOG_ENTRY_MSG_MAX_LEN];

    TEST_ASSERT_TRUE(logger_get_entry(0, type_buf, msg_buf));
    TEST_ASSERT_EQUAL_STRING("first", msg_buf);

    TEST_ASSERT_TRUE(logger_get_entry(2, type_buf, msg_buf));
    TEST_ASSERT_EQUAL_STRING("third", msg_buf);
}

TEST_CASE("logger_get_entry out-of-range index fails cleanly instead of reading garbage", "[logger][requires_hardware]")
{
    erase_log_namespace();
    logger_init();
    logger_log_event("BOOT", "only entry");

    char type_buf[16];
    char msg_buf[LOG_ENTRY_MSG_MAX_LEN];

    TEST_ASSERT_FALSE(logger_get_entry(1, type_buf, msg_buf));   // one past the end
    TEST_ASSERT_FALSE(logger_get_entry(999, type_buf, msg_buf)); // wildly out of range
}

TEST_CASE("ring buffer wraps correctly at SECURE_LOG_MAX_ENTRIES and discards the oldest entry", "[logger][requires_hardware][slow]")
{
    // This is the core "ring buffer wrap" boundary test the proposal calls
    // for. Fill the buffer to exactly capacity, then write one more and
    // confirm: (a) the count stays capped rather than growing unbounded,
    // and (b) the oldest entry ("event 0") was evicted while the newest
    // ("event N") is retrievable.
    erase_log_namespace();
    logger_init();

    for (int i = 0; i < SECURE_LOG_MAX_ENTRIES; i++) {
        char msg[32];
        snprintf(msg, sizeof(msg), "event %d", i);
        logger_log_event("INTEGRITY", msg);
    }
    TEST_ASSERT_EQUAL_UINT32(SECURE_LOG_MAX_ENTRIES, logger_get_entry_count());

    // One more push should wrap: count stays at capacity, oldest entry drops.
    logger_log_event("INTEGRITY", "event overflow");
    TEST_ASSERT_EQUAL_UINT32(SECURE_LOG_MAX_ENTRIES, logger_get_entry_count());

    char type_buf[16];
    char msg_buf[LOG_ENTRY_MSG_MAX_LEN];

    // Oldest retained entry should now be "event 1", not "event 0".
    TEST_ASSERT_TRUE(logger_get_entry(0, type_buf, msg_buf));
    TEST_ASSERT_EQUAL_STRING("event 1", msg_buf);

    // Newest entry should be the overflow write.
    TEST_ASSERT_TRUE(logger_get_entry(SECURE_LOG_MAX_ENTRIES - 1, type_buf, msg_buf));
    TEST_ASSERT_EQUAL_STRING("event overflow", msg_buf);
}

TEST_CASE("logger_log_event truncates an over-length message rather than overflowing the buffer", "[logger][requires_hardware]")
{
    erase_log_namespace();
    logger_init();

    char long_msg[256];
    memset(long_msg, 'A', sizeof(long_msg) - 1);
    long_msg[sizeof(long_msg) - 1] = '\0';

    logger_log_event("INTEGRITY", long_msg);

    char type_buf[16];
    char msg_buf[LOG_ENTRY_MSG_MAX_LEN];
    TEST_ASSERT_TRUE(logger_get_entry(0, type_buf, msg_buf));
    // Retrieved message must never exceed the entry's allocated size.
    TEST_ASSERT_TRUE(strlen(msg_buf) < LOG_ENTRY_MSG_MAX_LEN);
}
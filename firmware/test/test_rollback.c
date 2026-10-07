#include "unity.h"
#include "rollback.h"
#include "nvs_flash.h"
#include "nvs.h"

// Each test gets a clean NVS partition so rollback state from a previous
// test case can't leak into the next one and produce a false pass/fail.
static void erase_rollback_namespace(void)
{
    nvs_handle_t handle;
    if (nvs_open("rb_prot", NVS_READWRITE, &handle) == ESP_OK) {
        nvs_erase_all(handle);
        nvs_commit(handle);
        nvs_close(handle);
    }
}

TEST_CASE("rollback_init seeds baseline version on first-ever boot", "[rollback][requires_hardware]")
{
    erase_rollback_namespace();

    rollback_init();

    // ROLLBACK_BASELINE_VERSION is 1 (firmware_config.h) - version 1 should
    // be allowed, version 0 should not.
    TEST_ASSERT_TRUE(rollback_check_version(1));
    TEST_ASSERT_FALSE(rollback_check_version(0));
}

TEST_CASE("rollback_check_version rejects a version below the floor", "[rollback][requires_hardware]")
{
    erase_rollback_namespace();
    rollback_init();

    TEST_ASSERT_FALSE(rollback_check_version(-1));
}

TEST_CASE("rollback_check_version allows a version at or above the floor", "[rollback][requires_hardware]")
{
    erase_rollback_namespace();
    rollback_init();

    TEST_ASSERT_TRUE(rollback_check_version(1));
    TEST_ASSERT_TRUE(rollback_check_version(5));
}

TEST_CASE("rollback_commit_version advances the floor and persists across reinit", "[rollback][requires_hardware]")
{
    erase_rollback_namespace();
    rollback_init();

    rollback_commit_version(3);

    // Re-run init to simulate a reboot - the advanced floor must survive.
    rollback_init();
    TEST_ASSERT_TRUE(rollback_check_version(3));
    TEST_ASSERT_FALSE(rollback_check_version(2));
}

TEST_CASE("rollback_commit_version never moves the floor backward (monotonic)", "[rollback][requires_hardware]")
{
    erase_rollback_namespace();
    rollback_init();

    rollback_commit_version(5);
    rollback_commit_version(2);  // attempted rollback commit - must be ignored

    rollback_init();
    // Floor should still be 5, not 2 - version 3 must still be rejected.
    TEST_ASSERT_FALSE(rollback_check_version(3));
    TEST_ASSERT_TRUE(rollback_check_version(5));
}

TEST_CASE("simulated rollback attack: reflashing an older signed image is rejected after floor advances", "[rollback][requires_hardware]")
{
    // Mirrors the proposal's described attack scenario directly: device
    // runs v3, floor advances to 3, attacker reflashes the older v1 image.
    erase_rollback_namespace();
    rollback_init();
    rollback_commit_version(3);

    rollback_init();  // simulates reboot into the (attacker-supplied) old image
    bool old_image_boot_allowed = rollback_check_version(1);

    TEST_ASSERT_FALSE(old_image_boot_allowed);
}
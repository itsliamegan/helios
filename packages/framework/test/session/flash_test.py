from luna.test.assertion import assert_eq

from helios.session import Flash


def test_gets_flash_value():
	flash = Flash({"notice": "Saved"})

	assert_eq(flash.get("notice"), "Saved")


def test_gets_default_for_missing_flash():
	flash = Flash()

	assert_eq(
		[flash.get("notice"), flash.get("notice", "None yet")], [None, "None yet"]
	)

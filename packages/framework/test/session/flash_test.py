from luna.test.assertion import assert_eq, assert_in, assert_is, assert_raises

from helios.session import Flash


def test_gets_flash_value():
	flash = Flash({"notice": "Saved"})

	assert_eq(flash.get("notice"), "Saved")


def test_gets_default_for_missing_flash():
	flash = Flash()

	assert_eq(
		[flash.get("notice"), flash.get("notice", "None yet")], [None, "None yet"]
	)


def test_closed_flash_refuses_setting_items():
	flash = Flash()
	flash.close()

	with assert_raises(RuntimeError) as raised:
		flash["notice"] = "Saved"
	assert_is(type(raised.exception), RuntimeError)


def test_closed_flash_still_reads():
	flash = Flash({"notice": "Saved"})
	flash.close()

	assert_eq(flash["notice"], "Saved")
	assert_eq(flash.get("notice"), "Saved")
	assert_in("notice", flash)

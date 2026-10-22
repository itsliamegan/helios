from luna.test.assertion import assert_eq

from helios.session import Flashes


def test_gets_flash_value():
	flashes = Flashes({"notice": "Saved"})

	assert_eq(flashes.get("notice"), "Saved")


def test_gets_default_for_missing_flash():
	flashes = Flashes()

	assert_eq(
		[flashes.get("notice"), flashes.get("notice", "None yet")], [None, "None yet"]
	)

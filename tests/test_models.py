from awtrix_mcp.models import (
    AppPayload,
    DeviceSettings,
    DeviceStats,
    NotificationPayload,
    TextSegment,
)


def test_text_segment_serializes_to_wire_keys():
    segment = TextSegment(text="FAIL", color="FF0000")
    assert segment.model_dump(by_alias=True, exclude_none=True) == {
        "t": "FAIL",
        "c": "FF0000",
    }


def test_app_payload_defaults():
    payload = AppPayload(text="hi")
    assert payload.duration == 5
    assert payload.repeat == -1
    assert payload.rainbow is False


def test_app_payload_text_as_plain_string_serializes():
    payload = AppPayload(text="hi")
    dumped = payload.model_dump(by_alias=True, exclude_none=True)
    assert dumped["text"] == "hi"


def test_app_payload_text_as_segments_serializes():
    payload = AppPayload(text=[TextSegment(text="FAIL", color="FF0000")])
    dumped = payload.model_dump(by_alias=True, exclude_none=True)
    assert dumped["text"] == [{"t": "FAIL", "c": "FF0000"}]


def test_notification_payload_defaults():
    payload = NotificationPayload(text="hi")
    assert payload.hold is False
    assert payload.duration == 5
    assert payload.wakeup is False
    assert payload.stack is True


def test_device_stats_round_trip_from_real_sample():
    sample = {
        "bat": 97,
        "bat_raw": 660,
        "lux": "8",
        "ldr_raw": 547,
        "ram": 152948,
        "bri": 120,
        "temp": "25",
        "hum": "29",
        "uptime": "76",
        "wifi_signal": -41,
        "up_available": False,
        "messages": 1,
        "version": "0.68",
        "indicator1": True,
        "indicator2": False,
        "indicator3": True,
    }
    stats = DeviceStats.model_validate(sample)
    assert stats.battery == 97
    assert stats.ram_free == 152948
    assert stats.lux == "8"
    assert stats.temp == "25"


def test_device_stats_tolerates_missing_optional_fields():
    stats = DeviceStats.model_validate({"bat": 50, "lux": "1", "temp": "20", "ram": 1000})
    assert stats.charging is None
    assert stats.active_app is None


def test_device_stats_tolerates_unknown_extra_fields():
    stats = DeviceStats.model_validate(
        {
            "bat": 50,
            "lux": "1",
            "temp": "20",
            "ram": 1000,
            "wifi_signal": -41,
            "unknown_future_field": 1,
        }
    )
    assert stats.battery == 50


def test_device_settings_alias_mapping():
    settings = DeviceSettings.model_validate({"BRI": 120, "MATP": True, "ATRANS": False})
    assert settings.brightness == 120
    assert settings.power is True
    assert settings.transitions is False
    assert settings.model_dump(by_alias=True) == {
        "BRI": 120,
        "MATP": True,
        "ATRANS": False,
    }


def test_device_settings_partial_update_omits_unset_fields():
    settings = DeviceSettings(brightness=80, power=True)
    assert settings.transitions is None
    assert settings.model_dump(by_alias=True, exclude_none=True) == {
        "BRI": 80,
        "MATP": True,
    }


def test_app_payload_lifetime_mode_serializes_to_wire_alias():
    payload = AppPayload(text="hi", lifetime_mode=1)
    dumped = payload.model_dump(by_alias=True, exclude_none=True)
    assert dumped["lifetimeMode"] == 1

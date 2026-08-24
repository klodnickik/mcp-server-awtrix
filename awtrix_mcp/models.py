"""Pydantic domain models for the AWTRIX 3 device wire protocol."""

from pydantic import BaseModel, ConfigDict, Field

ColorValue = str | list[int] | None


class TextSegment(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    text: str = Field(validation_alias="t", serialization_alias="t")
    color: ColorValue = Field(default=None, validation_alias="c", serialization_alias="c")


class AppPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    text: str | list[TextSegment]
    icon: str | None = None
    duration: int = 5
    repeat: int = -1
    rainbow: bool = False
    color: ColorValue = None
    lifetime: int | None = None
    lifetime_mode: int | None = Field(default=None, validation_alias="lifetimeMode", serialization_alias="lifetimeMode")
    save: bool = False


class NotificationPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    text: str | list[TextSegment]
    icon: str | None = None
    color: ColorValue = None
    sound: str | None = None
    rtttl: str | None = None
    hold: bool = False
    duration: int = 5
    wakeup: bool = False
    stack: bool = True


class DeviceStats(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    battery: int = Field(validation_alias="bat", serialization_alias="bat")
    # unconfirmed on real hardware
    charging: bool | None = None
    lux: str
    ram_free: int = Field(validation_alias="ram", serialization_alias="ram")
    temp: str
    # unconfirmed on real hardware
    active_app: str | None = None


class DeviceSettings(BaseModel):
    """Partial-update model: all fields default to None and are omitted from the
    wire payload via model_dump(exclude_none=True), so only fields explicitly set
    are sent to the device."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    brightness: int | None = Field(default=None, validation_alias="BRI", serialization_alias="BRI")
    power: bool | None = Field(default=None, validation_alias="MATP", serialization_alias="MATP")
    # unconfirmed on real hardware
    transitions: bool | None = Field(default=None, validation_alias="ATRANS", serialization_alias="ATRANS")

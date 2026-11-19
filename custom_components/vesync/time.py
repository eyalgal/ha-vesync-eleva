"""Support for VeSync time entities (Eleva Quiet Period)."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import time
from typing import override

from pyvesync.base_devices import VeSyncBaseDevice
from pyvesync.device_container import DeviceContainer

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .common import rgetattr
from .const import VS_DEVICES, VS_DISCOVERY
from .coordinator import VesyncConfigEntry, VeSyncDataCoordinator
from .entity import VeSyncBaseEntity

PARALLEL_UPDATES = 1


def _seconds_to_time(seconds: int | None) -> time | None:
    if seconds is None:
        return None
    seconds %= 86400
    return time(seconds // 3600, (seconds % 3600) // 60, seconds % 60)


def _time_to_seconds(value: time) -> int:
    return value.hour * 3600 + value.minute * 60 + value.second


@dataclass(frozen=True, kw_only=True)
class VeSyncTimeEntityDescription(TimeEntityDescription):
    """Describe a VeSync time entity."""

    attr: str
    set_fn: Callable[[VeSyncBaseDevice, int], Awaitable[bool]]


TIME_DESCRIPTIONS: tuple[VeSyncTimeEntityDescription, ...] = (
    VeSyncTimeEntityDescription(
        key="quiet_period_start",
        translation_key="quiet_period_start",
        entity_category=EntityCategory.CONFIG,
        attr="quiet_period_start",
        set_fn=lambda device, value: device.set_quiet_period(start=value),
    ),
    VeSyncTimeEntityDescription(
        key="quiet_period_end",
        translation_key="quiet_period_end",
        entity_category=EntityCategory.CONFIG,
        attr="quiet_period_end",
        set_fn=lambda device, value: device.set_quiet_period(end=value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VesyncConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up time entities."""

    coordinator = config_entry.runtime_data

    @callback
    def discover(devices: list[VeSyncBaseDevice]) -> None:
        """Add new devices to platform."""
        _setup_entities(devices, async_add_entities, coordinator)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, VS_DISCOVERY.format(VS_DEVICES), discover)
    )

    _setup_entities(
        config_entry.runtime_data.manager.devices, async_add_entities, coordinator
    )


@callback
def _setup_entities(
    devices: DeviceContainer | list[VeSyncBaseDevice],
    async_add_entities: AddConfigEntryEntitiesCallback,
    coordinator: VeSyncDataCoordinator,
) -> None:
    """Add time entities for devices that support a Quiet Period."""
    async_add_entities(
        VeSyncTimeEntity(dev, description, coordinator)
        for dev in devices
        for description in TIME_DESCRIPTIONS
        if hasattr(dev, "set_quiet_period")
        and rgetattr(dev, f"state.{description.attr}") is not None
    )


class VeSyncTimeEntity(VeSyncBaseEntity, TimeEntity):
    """A VeSync time setting."""

    entity_description: VeSyncTimeEntityDescription

    def __init__(
        self,
        device: VeSyncBaseDevice,
        description: VeSyncTimeEntityDescription,
        coordinator: VeSyncDataCoordinator,
    ) -> None:
        """Initialize the time entity."""
        super().__init__(device, coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}-{description.key}"

    @property
    @override
    def native_value(self) -> time | None:
        """Return the configured time."""
        return _seconds_to_time(getattr(self.device.state, self.entity_description.attr))

    @override
    async def async_set_value(self, value: time) -> None:
        """Set the time."""
        if not await self.entity_description.set_fn(
            self.device, _time_to_seconds(value)
        ):
            if self.device.last_response:
                raise HomeAssistantError(self.device.last_response.message)
            raise HomeAssistantError("Failed to set time, no response found.")
        self.async_write_ha_state()

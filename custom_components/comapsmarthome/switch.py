from datetime import timedelta
import logging
from typing import Any
from bidict import bidict
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.helpers.device_registry import DeviceInfo


from homeassistant.const import (
    CONF_USERNAME,
    CONF_PASSWORD,
)

from . import ComapCoordinator, ComapClient

from .const import (
    DOMAIN,
)

SCAN_INTERVAL = timedelta(minutes=5)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities,
) -> None:
    config = hass.data[DOMAIN][config_entry.entry_id]
    client = ComapClient(username=config[CONF_USERNAME], password=config[CONF_PASSWORD])
    async_add_entities([ComapHousingSensor(client)], update_before_add=True)


class ComapHousingSensor(SwitchEntity):
    def __init__(self, client) -> None:
        super().__init__()
        self.client = client
        self.housing = client.housing
        housing = client.get_housings()[0]
        self._name = housing.get("name")
        self._is_on = None
        self._attr_device_class = SwitchDeviceClass.SWITCH

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.unique_id)
            },
            name=self.name,
            manufacturer="comap",
        )

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self.client.housing

    @property
    def is_on(self):
        """If the sensor is currently on or off."""
        return self._is_on

    async def async_update(self):
        zones = await self.client.get_zones()
        self._is_on = True if zones["heating_system_state"] == "on" else False

    async def async_turn_on(self, **kwargs: Any) -> None:
        return await self.client.turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        return await self.client.turn_off()

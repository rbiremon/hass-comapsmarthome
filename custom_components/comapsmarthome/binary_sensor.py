import logging
from typing import Any
from bidict import bidict
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from datetime import datetime, timedelta, timezone
from homeassistant.helpers.device_registry import DeviceInfo


from homeassistant.const import (
    CONF_USERNAME,
    CONF_PASSWORD,
)

from . import ComapCoordinator, ComapClient

from .const import (
    DOMAIN,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities,
) -> None:
    config = hass.data[DOMAIN][config_entry.entry_id]
    client = ComapClient(username=config[CONF_USERNAME], password=config[CONF_PASSWORD])
    coordinator = ComapCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()
    entities = list()
    for zone_id, zone in coordinator.data.items():
        if (
            "last_presence_detected" in zone.keys()
            and zone["last_presence_detected"] != None
        ):
            entities.append(
                ComapPresenceSensor(
                    coordinator=coordinator, zone_id=zone_id, client=client
                )
            )
    # entities: entities
    async_add_entities(entities)


class ComapPresenceSensor(CoordinatorEntity[ComapCoordinator], BinarySensorEntity):
    def __init__(self, coordinator: ComapCoordinator, zone_id, client):
        super().__init__(coordinator)
        self.client = client
        self.coordinator = coordinator
        self.zone_id = zone_id
        self._attr_device_class = BinarySensorDeviceClass.OCCUPANCY
        self._name = self.coordinator.data[self.zone_id]["title"] + " presence"
        self._id = zone_id + "_presence"
        self._is_on = None
        self.attrs = dict()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.zone_id)
            },
            name=self.coordinator.data[self.zone_id]["title"],
            manufacturer="comap",
        )

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self._id

    @property
    def is_on(self):
        """If the sensor is currently on or off."""
        return self._is_on

    @property
    def extra_state_attributes(self) -> dict:
        return self.attrs

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._is_on = self.is_occupied(
            self.coordinator.data[self.zone_id]["last_presence_detected"]
        )
        self.attrs.update(
            {
                "last_presence_detected": self.coordinator.data[self.zone_id][
                    "last_presence_detected"
                ],
            }
        )
        self.async_write_ha_state()

    @staticmethod
    def is_occupied(timestamp):
        now = datetime.now(timezone.utc)
        presence = datetime.fromisoformat(timestamp)
        two_minutes = timedelta(minutes=2)
        if now - presence < two_minutes:
            return True
        else:
            return False

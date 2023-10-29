import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.device_registry import DeviceInfo

from homeassistant.helpers.typing import (
    ConfigType,
    HomeAssistantType,
)

from homeassistant.const import (
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    CONF_PASSWORD,
)

from datetime import timedelta
from .comap import ComapClient
import voluptuous as vol
from typing import Optional, Any


from .const import (
    ATTR_ADDRESS,
    SERVICE_SET_AWAY,
    SERVICE_SET_HOME,
    DOMAIN,
    ATTR_AVL_SCHDL,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL): cv.Number,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities,
):
    config = hass.data[DOMAIN][config_entry.entry_id]
    await async_setup_platform(hass, config, async_add_entities)


async def async_setup_platform(
    hass: HomeAssistantType,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the comapsmarthome platform."""

    client = ComapClient(username=config[CONF_USERNAME], password=config[CONF_PASSWORD])
    housing = [ComapHousingSensor(client)]
    async_add_entities(housing, update_before_add=True)

    async def set_away(call):
        """Set home away."""
        await client.leave_home()

    async def set_home(call):
        """Set home."""
        await client.return_home()

    hass.services.async_register(DOMAIN, SERVICE_SET_AWAY, set_away)
    hass.services.async_register(DOMAIN, SERVICE_SET_HOME, set_home)

    return True


class ComapHousingSensor(Entity):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.housing = client.housing
        self._name = client.get_housings()[0].get("name")
        self._state = None
        self._available = True
        self.attrs: dict[str, Any] = {}

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self.client.housing

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def state(self) -> Optional[str]:
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.attrs

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

    async def async_update(self):
        housings = await self.hass.async_add_executor_job(self.client.get_housings)
        self._name = housings[0].get("name")
        self.attrs[ATTR_ADDRESS] = housings[0].get("address")
        r = await self.get_schedules()
        self.attrs[ATTR_AVL_SCHDL] = self.parse_schedules(r)

    async def get_schedules(self):
        r = await self.client.get_schedules()
        return r

    def parse_schedules(self, r) -> dict[str, str]:
        schedules = {}
        for schedule in r:
            schedules.update({schedule["id"]: schedule["title"]})
        return schedules

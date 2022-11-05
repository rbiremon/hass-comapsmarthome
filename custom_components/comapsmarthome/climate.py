import logging
from bidict import bidict
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.components.climate import (
    ClimateEntity,
    HVACMode,
    ClimateEntityFeature,
)

from homeassistant.components.climate.const import (
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_AWAY
)

from homeassistant.helpers.typing import (
    ConfigType,
    DiscoveryInfoType,
    HomeAssistantType,
)

from homeassistant.const import (
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    CONF_PASSWORD,
    TEMP_CELSIUS,
)

from typing import Optional, Any
from datetime import timedelta
from .comap import ComapClient
import voluptuous as vol


from .const import (
    ATTR_ADDRESS,
    DOMAIN,
    ATTR_AVL_SCHDL,
    SERVICE_SET_SCHEDULE,
    ATTR_SCHEDULE_NAME,
)

from . import ComapCoordinator

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL): cv.Number,
    }
)

PRESET_MODE_MAP = bidict({
            "stop": "off",
            "frost_protection": PRESET_AWAY,
            "eco": PRESET_ECO,
            "comfort": PRESET_COMFORT,
            "comfort_minus1": "comfort -1",
            "comfort_minus2": "comfort -2",
        })

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
    discovery_info: Optional[DiscoveryInfoType] = None,
) -> None:
    """Set up the comapsmarthome platform."""

    client = ComapClient(username=config[CONF_USERNAME],password=config[CONF_PASSWORD])
    coordinator = ComapCoordinator(hass,client)

    housing_details = await hass.async_add_executor_job(client.get_zones)
    zones = [ComapZoneThermostat(coordinator, client, zone) for zone in housing_details.get("zones")]

    await coordinator.async_config_entry_first_refresh()
    async_add_entities(zones, update_before_add=True)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_SCHEDULE,
        {vol.Required(ATTR_SCHEDULE_NAME): cv.string},
        "service_set_schedule",
    )

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

    async def async_update(self):
        housings = await self.hass.async_add_executor_job(
            self.client.get_housings)
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


class ComapZoneThermostat(CoordinatorEntity[ComapCoordinator],ClimateEntity):
    _attr_target_temperature_step = "0.5"
    _attr_temperature_unit = TEMP_CELSIUS
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_preset_modes = [
        "off",
        PRESET_AWAY,
        "comfort -1",
        "comfort -2",
        PRESET_ECO,
        PRESET_COMFORT,
    ]

    def __init__(self, coordinator: ComapCoordinator, client, zone):
        super().__init__(coordinator)
        self.client = client
        self.zone_id = zone.get("id")
        self._name = zone.get("title")
        self._available = True
        self.set_point_type = zone.get("set_point_type")
        if (self.set_point_type == "custom_temperature")  | (self.set_point_type == "defined_temperature"):
            self.zone_type = "thermostat"
            self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
            self._current_temperature = zone.get("temperature")
            self._current_humidity = zone.get("humidity")
            if (self.set_point_type == "custom_temperature"):
                self._attr_target_temperature = zone.get("set_point").get("instruction")
            else:
                self.update_target_temperature(zone.get("set_point").get("instruction"))

        if self.set_point_type == "pilot_wire":
            self.zone_type = "pilot_wire"
            self._attr_preset_mode = self.map_preset_mode(
                zone.get("set_point").get("instruction")
            )
            self._attr_supported_features = ClimateEntityFeature.PRESET_MODE
        self._hvac_mode = self.map_hvac_mode(zone.get("heating_status"))
        self.attrs: dict[str, Any] = {}

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self.zone_id

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def current_temperature(self) -> float:
        return self._current_temperature

    @property
    def current_humidity(self) -> int:
        return self._current_humidity

    @property
    def hvac_mode(self):
        return self._hvac_mode

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.attrs

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.attrs.update(self.coordinator.data[self.zone_id])
        self.async_schedule_update_ha_state(force_refresh=True)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        await self.client.set_temporary_instruction(self.zone_id,self.map_comap_mode(preset_mode))
        await self.async_update()
    
    async def async_set_hvac_mode(self, hvac_mode: str) -> bool:
        """Set new hvac mode."""
        if (hvac_mode == HVACMode.OFF) & (self.zone_type == "pilot_wire"):
            await self.async_set_preset_mode("off")
        elif (hvac_mode == HVACMode.HEAT) & (self.zone_type == "pilot_wire"):
            await self.async_set_preset_mode(PRESET_COMFORT)
        elif (hvac_mode == HVACMode.OFF) & (self.zone_type == "thermostat"):
            await self.client.set_temporary_instruction(self.zone_id,8)
            await self.async_update()
        elif (hvac_mode == HVACMode.HEAT) & (self.zone_type == "thermostat"):
            await self.client.set_temporary_instruction(self.zone_id,20)
            await self.async_update()
    
    async def async_set_temperature(self, **kwargs) -> None:
            await self.client.set_temporary_instruction(self.zone_id,kwargs["temperature"])
            await self.async_update()

    async def async_update(self):
        zone_data = await self.hass.async_add_executor_job(
            self.client.get_zone, self.zone_id
        )
        self._current_temperature = zone_data.get("temperature")
        self._current_humidity = zone_data.get("humidity")
        self._hvac_mode = self.map_hvac_mode(zone_data.get("heating_status"))
        self.set_point_type = zone_data.get("set_point_type") 
        if self.zone_type == "thermostat":
            self.update_target_temperature(zone_data.get("set_point").get("instruction"))

    def map_hvac_mode(self, comap_mode):
        hvac_mode_map = {"cooling": HVACMode.OFF, "heating": HVACMode.HEAT}
        if comap_mode is None:
            return HVACMode.OFF
        else:
            return hvac_mode_map.get(comap_mode)

    def map_preset_mode(self, comap_mode):
        return PRESET_MODE_MAP.get(comap_mode)
    
    def map_comap_mode(self, ha_mode):
        return PRESET_MODE_MAP.inverse[ha_mode]
    
    def update_target_temperature(self, instruction):
        if self.set_point_type == "custom_temperature":
            self._attr_target_temperature = instruction
        elif self.set_point_type == "defined_temperature":
            try:
                temperatures = self.coordinator.data["temperatures"]
                if instruction in temperatures:
                    self._attr_target_temperature = temperatures[instruction]
                elif instruction in temperatures["connected"]:
                    self._attr_target_temperature = temperatures["connected"][instruction]
            except:
                self._attr_target_temperature = 0

    async def service_set_schedule(self, **kwargs: Any):
        '''Set schedule by id for the zone'''
        r = await self.client.set_schedule(self.zone_id, kwargs.get(ATTR_SCHEDULE_NAME))

        # Update the data
        await self.coordinator.async_request_refresh()

        return r

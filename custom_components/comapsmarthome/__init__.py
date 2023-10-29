"""ComapSmartHome custom component"""
import asyncio
import logging
from datetime import timedelta

import async_timeout
from jinja2 import TemplateAssertionError
from homeassistant import config_entries, core
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

from .comap import ComapClient, ComapClientException

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Set up platform from a ConfigEntry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    # Forward the setup to the sensor platform.
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "climate")
    )
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "binary_sensor")
    )

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "switch")
    )
    return True


class ComapCoordinator(DataUpdateCoordinator):
    """My custom coordinator."""

    def __init__(self, hass, comap_client):
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="ComapSmartHome",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=30),
        )
        self.client = comap_client

    async def _async_update_data(self) -> dict:
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(10):
                zones = await self.client.get_zones()
                zones_details = dict()
                for zone in zones["zones"]:
                    zone_detail = dict()
                    zone_detail.update(zone)
                    zones_details[zone["id"]] = zone_detail
                zone_schedules = await self.client.get_active_schedules()
                for zone in zone_schedules:
                    zones_details[zone["id"]].update(zone)
                temperatures = await self.client.get_custom_temperatures()
                return {
                    # **{zone["id"]: zone for zone in zone_schedules},
                    **zones_details,
                    "temperatures": temperatures,
                }
        except ComapClientException as err:
            # Raising ConfigEntryAuthFailed will cancel future updates
            # and start a config flow with SOURCE_REAUTH (async_step_reauth)
            raise ConfigEntryAuthFailed from err

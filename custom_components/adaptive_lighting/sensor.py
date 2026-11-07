"""Sensor platform for Adaptive Lighting."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_NAME, DOMAIN, ICON_BRIGHTNESS, ICON_COLOR_TEMP, SWITCH_DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Adaptive Lighting sensors."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    switch = data[SWITCH_DOMAIN]

    color_sensor = AdaptiveLightingColorTempSensor(hass, config_entry, switch)
    brightness_sensor = AdaptiveLightingBrightnessSensor(hass, config_entry, switch)

    async_add_entities([color_sensor, brightness_sensor], update_before_add=True)


class AdaptiveLightingSensorBase(SensorEntity):
    """Base class for Adaptive Lighting sensors."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        switch: Any,
    ) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._config_entry = config_entry
        self._switch = switch
        self._name = switch._name

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info matching the main Adaptive Lighting switch."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._name)},
            name=f"Adaptive Lighting: {self._name}",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        """Register update listener with the parent switch."""
        if hasattr(self._switch, "register_update_listener"):
            self.async_on_remove(
                self._switch.register_update_listener(self._async_handle_update),
            )

    @callback
    def _async_handle_update(self) -> None:
        """Handle updated settings from switch."""
        self.async_write_ha_state()


class AdaptiveLightingColorTempSensor(AdaptiveLightingSensorBase):
    """Sensor reporting target color temperature in Kelvin."""

    _attr_icon = ICON_COLOR_TEMP
    _attr_native_unit_of_measurement = "K"
    _attr_translation_key = "color_temperature"

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        switch: Any,
    ) -> None:
        """Initialize the color temperature sensor."""
        super().__init__(hass, config_entry, switch)
        self._attr_unique_id = f"{config_entry.entry_id}_color_temp"
        self._attr_name = "Color Temperature"

    @property
    def native_value(self) -> int | None:
        """Return the target color temperature in Kelvin."""
        return self._switch._settings.get("color_temp_kelvin")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        cct = self._switch._settings.get("color_temp_kelvin")
        min_cct = self._switch._sun_light_settings.min_color_temp
        max_cct = self._switch._sun_light_settings.max_color_temp

        factor: float | None = None
        if cct is not None and max_cct > min_cct:
            factor = round((cct - min_cct) / (max_cct - min_cct), 3)

        return {
            "color_temp_mired": self._switch._settings.get("color_temp_mired"),
            "normalized_factor": factor,
            "min_color_temp": min_cct,
            "max_color_temp": max_cct,
            "sun_position": self._switch._settings.get("sun_position"),
        }


class AdaptiveLightingBrightnessSensor(AdaptiveLightingSensorBase):
    """Sensor reporting target brightness percentage."""

    _attr_icon = ICON_BRIGHTNESS
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_translation_key = "brightness"

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        switch: Any,
    ) -> None:
        """Initialize the brightness sensor."""
        super().__init__(hass, config_entry, switch)
        self._attr_unique_id = f"{config_entry.entry_id}_brightness"
        self._attr_name = "Brightness"

    @property
    def native_value(self) -> float | None:
        """Return the target brightness percentage."""
        val = self._switch._settings.get("brightness_pct")
        if val is None:
            return None
        return round(float(val), 1)

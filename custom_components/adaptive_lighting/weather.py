"""Open-Meteo weather integration for Adaptive Lighting."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval

_LOGGER = logging.getLogger(__name__)

URL_TEMPLATE = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude={lat}&longitude={lon}"
    "&current=cloud_cover,direct_radiation,diffuse_radiation"
    "&hourly=cloud_cover,direct_radiation"
    "&forecast_days=2"
    "&timezone=auto"
)


class WeatherCoordinator:
    """Fetches and caches weather and solar radiation forecast data."""

    def __init__(self, hass: HomeAssistant, interval_seconds: int = 600) -> None:
        """Initialize the weather coordinator."""
        self.hass = hass
        self.interval = timedelta(seconds=interval_seconds)
        self.cloud_cover: float = 0.0
        self.direct_radiation: float = 0.0
        self.diffuse_radiation: float = 0.0
        self.hourly_cloud_cover: list[dict[str, Any]] = []
        self.last_updated: datetime | None = None
        self._unsub: Any = None

    async def async_start(self) -> None:
        """Start periodic weather updates."""
        await self.async_update()
        self._unsub = async_track_time_interval(
            self.hass,
            self._async_scheduled_update,
            self.interval,
        )

    async def _async_scheduled_update(self, _now: datetime) -> None:
        """Scheduled update callback."""
        await self.async_update()

    async def async_update(self) -> None:
        """Fetch latest weather from Open-Meteo."""
        lat = self.hass.config.latitude
        lon = self.hass.config.longitude
        if not lat or not lon:
            _LOGGER.debug(
                "Home Assistant latitude/longitude not configured; skipping weather update",
            )
            return

        url = URL_TEMPLATE.format(lat=lat, lon=lon)
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    current = data.get("current", {})
                    self.cloud_cover = float(current.get("cloud_cover", 0.0))
                    self.direct_radiation = float(current.get("direct_radiation", 0.0))
                    self.diffuse_radiation = float(current.get("diffuse_radiation", 0.0))
                    self.last_updated = datetime.now(timezone.utc)
                    _LOGGER.debug(
                        "Open-Meteo weather updated: cloud_cover=%.1f%%, direct_rad=%.1f W/m²",
                        self.cloud_cover,
                        self.direct_radiation,
                    )
                else:
                    _LOGGER.warning("Open-Meteo API returned HTTP %d", resp.status)
        except Exception as err:
            _LOGGER.debug("Could not fetch weather from Open-Meteo: %s", err)

    def stop(self) -> None:
        """Stop tracking."""
        if self._unsub:
            self._unsub()
            self._unsub = None

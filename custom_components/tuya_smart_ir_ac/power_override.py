"""Read an IR AC's on/off state from the smart plug that feeds it.

An IR AC only knows the last command Home Assistant itself sent, so a press on
the wall remote never reaches HA. A power-metering plug in front of the AC
does: measured on one unit, off = 0 W (3-4 W for a few seconds while it shuts
down), on = 8-30 W with only the fan running and 70-830 W with the compressor.
A reading at or above the threshold therefore means the unit is on.

The mapping lives outside the integration, so updates never overwrite it:
<config>/tuya_smart_ir_ac_power.json

    {
      "on_watts": 6,
      "power_sensors": {
        "<tuya ir climate device_id>": "sensor.<plug_power_sensor>"
      }
    }

No file, or a climate that is not listed: the integration behaves as upstream.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__package__)

CONFIG_FILE = "tuya_smart_ir_ac_power.json"
DEFAULT_ON_WATTS = 6.0

POWER_SENSORS: dict[str, str] = {}
ON_WATTS = DEFAULT_ON_WATTS


def _load() -> None:
    """Read the mapping once. Runs at import, which HA does in an executor."""
    global ON_WATTS
    # custom_components/tuya_smart_ir_ac/power_override.py -> <config>/
    path = Path(__file__).resolve().parents[2] / CONFIG_FILE
    if not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        POWER_SENSORS.update({str(k): str(v) for k, v in data.get("power_sensors", {}).items()})
        ON_WATTS = float(data.get("on_watts", DEFAULT_ON_WATTS))
    except (OSError, ValueError, TypeError, AttributeError) as err:
        _LOGGER.warning("Ignoring %s: %s", path, err)
        return
    _LOGGER.info("Power plugs for %d IR climate(s) from %s", len(POWER_SENSORS), path)


_load()


def power_sensor(climate_id: str | None) -> str | None:
    """The power sensor watching this climate, if one is mapped."""
    return POWER_SENSORS.get(climate_id or "")


def powered(hass: HomeAssistant | None, climate_id: str | None) -> bool | None:
    """True/False from the plug; None when there is no usable reading."""
    sensor = power_sensor(climate_id)
    if hass is None or sensor is None:
        return None
    state = hass.states.get(sensor)
    if state is None:
        return None
    try:
        return float(state.state) >= ON_WATTS
    except (TypeError, ValueError):
        return None  # unavailable/unknown: fall back to the IR state

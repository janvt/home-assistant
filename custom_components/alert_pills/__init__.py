"""Alert pills: small icons on the Mobile dashboard for conditions worth knowing about.

The pills themselves are defined in `dashboards/mobile-alerts/pills.py` and
pushed here by its `sync.py` through `alert_pills.load`. Which pills are on,
which only get a card, and how many fit in the row are options of this
integration, so they can be changed from the phone.
"""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse, callback
from homeassistant.exceptions import ServiceValidationError, TemplateError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import ConfigType

from .const import (
    DOMAIN,
    SERVICE_DISMISS,
    SERVICE_LOAD,
    SERVICE_RESTORE,
    SERVICE_TOGGLE_DISMISS,
)
from .manager import PillManager

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type AlertPillsConfigEntry = ConfigEntry[PillManager]

PILL_SCHEMA = vol.Schema({
    vol.Required("key"): vol.Match(r"^[a-z0-9]+(_[a-z0-9]+)*$"),
    vol.Required("name"): cv.string,
    vol.Required("group"): cv.string,
    vol.Required("icon"): cv.icon,
    vol.Required("color"): cv.string,
    vol.Required("state"): cv.string,
    vol.Optional("content"): vol.Any(None, cv.string),
    vol.Optional("critical", default=False): cv.boolean,
})
LOAD_SCHEMA = vol.Schema({
    vol.Required("pills"): [PILL_SCHEMA],
    vol.Optional("groups", default=[]): [cv.string],
    vol.Optional("dry_run", default=False): cv.boolean,
})
KEY_SCHEMA = vol.Schema({vol.Required("key"): cv.string})


def _manager(hass: HomeAssistant) -> PillManager:
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        raise ServiceValidationError("Alert pills is not set up")
    return entries[0].runtime_data


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    async def load(call: ServiceCall) -> ServiceResponse:
        manager = _manager(hass)
        pills = [{k: v for k, v in p.items() if v is not None} for p in call.data["pills"]]
        keys = [p["key"] for p in pills]
        if len(keys) != len(set(keys)):
            raise ServiceValidationError(f"duplicate pill keys: {sorted({k for k in keys if keys.count(k) > 1})}")
        for p in pills:
            for field in ("state", "color", "content"):
                if p.get(field):
                    try:
                        Template(p[field], hass).ensure_valid()
                    except TemplateError as err:
                        raise ServiceValidationError(f"{p['key']} {field}: {err}") from err
        old, new = manager.by_key, {p["key"]: p for p in pills}
        diff = {
            "added": [k for k in new if k not in old],
            "removed": [k for k in old if k not in new],
            "changed": [k for k in new if k in old and new[k] != old[k]],
        }
        order_changed = list(old) != list(new) or manager.groups != call.data["groups"]
        if not call.data["dry_run"] and (any(diff.values()) or order_changed):
            await manager.async_set_definitions(pills, call.data["groups"])
            await hass.config_entries.async_reload(manager.entry.entry_id)
        return {**diff, "order_changed": order_changed}

    def keyed(action):
        @callback
        def handler(call: ServiceCall) -> None:
            manager = _manager(hass)
            key = call.data["key"]
            pill = manager.by_key.get(key)
            if pill is None:
                raise ServiceValidationError(f"no pill {key!r}")
            if pill.get("critical") and action != "restore":
                raise ServiceValidationError(f"{pill['name']} is a safety alert and can't be dismissed")
            dismissed = manager.is_dismissed(key)
            if action == "restore" or (action == "toggle" and dismissed):
                manager.restore(key)
            elif not dismissed and manager.on_since.get(key) is not None:
                manager.dismiss(key)
        return handler

    hass.services.async_register(DOMAIN, SERVICE_LOAD, load, LOAD_SCHEMA, supports_response=SupportsResponse.OPTIONAL)
    hass.services.async_register(DOMAIN, SERVICE_DISMISS, keyed("dismiss"), KEY_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_RESTORE, keyed("restore"), KEY_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_TOGGLE_DISMISS, keyed("toggle"), KEY_SCHEMA)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: AlertPillsConfigEntry) -> bool:
    manager = PillManager(hass, entry)
    await manager.async_load()
    entry.runtime_data = manager

    # Pills dropped from pills.py lose their entities.
    registry = er.async_get(hass)
    keep = {p["key"] for p in manager.pills} | {"active", "row"}
    for ent in er.async_entries_for_config_entry(registry, entry.entry_id):
        if ent.unique_id not in keep:
            registry.async_remove(ent.entity_id)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Render once everything else is up, so a pill that was on before a
    # restart doesn't read half-loaded sensors, turn off and lose its dismissal.
    @callback
    def start(_: Any) -> None:
        manager.async_start()

    entry.async_on_unload(async_at_started(hass, start))
    entry.async_on_unload(manager.async_stop)
    entry.async_on_unload(entry.add_update_listener(_options_updated))
    return True


async def _options_updated(hass: HomeAssistant, entry: AlertPillsConfigEntry) -> None:
    entry.runtime_data.async_options_updated()


async def async_unload_entry(hass: HomeAssistant, entry: AlertPillsConfigEntry) -> bool:
    # A reload reads the store straight back: write the delayed save now.
    await entry.runtime_data.async_flush()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: AlertPillsConfigEntry) -> None:
    await PillManager(hass, entry).async_remove_store()

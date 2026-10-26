"""Evaluates the pills and works out which show.

One manager per config entry. It keeps the pill definitions (pushed by
`alert_pills.load`), renders each enabled pill's templates, and remembers when
each pill turned on and when it was dismissed. That memory is stored, so an HA
restart no longer brings dismissed pills back.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.event import (
    TrackTemplate,
    TrackTemplateResult,
    TrackTemplateResultInfo,
    async_track_template_result,
)
from homeassistant.helpers.storage import Store
from homeassistant.helpers.template import Template, result_as_boolean

from . import logic
from .const import (
    CONF_CARD_ONLY,
    CONF_DISABLED,
    CONF_DISABLED_GROUPS,
    CONF_PLACES,
    DEFAULT_PLACES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
STORAGE_VERSION = 1

Listener = Callable[[set[str] | None], None]


@dataclass
class PillState:
    on: bool | None = None  # None: not evaluated (switched off, or not yet)
    error: str | None = None
    color: str = ""
    content: str = ""


class PillManager:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, DOMAIN)
        self.pills: list[dict[str, Any]] = []
        self.groups: list[str] = []
        self.states: dict[str, PillState] = {}
        self.on_since: dict[str, float] = {}
        self.dismissed_at: dict[str, float] = {}
        # Pills that were on when HA stopped: they keep their on_since if
        # they're still on at the first evaluation, so dismissals survive.
        self._was_on: set[str] = set()
        self._trackers: list[TrackTemplateResultInfo] = []
        self._listeners: list[Listener] = []
        self.shown: list[str] = []
        self.row: list[str] = []
        self.overflow = 0

    # ── definitions and storage ──────────────────────────────────────────────
    @property
    def by_key(self) -> dict[str, dict[str, Any]]:
        return {p["key"]: p for p in self.pills}

    async def async_load(self) -> None:
        data = await self._store.async_load() or {}
        self.pills = data.get("pills", [])
        self.groups = data.get("groups", [])
        self.dismissed_at = data.get("dismissed", {})
        self.on_since = data.get("on_since", {})
        self._was_on = set(self.on_since)

    def _data(self) -> dict[str, Any]:
        return {"pills": self.pills, "groups": self.groups, "dismissed": self.dismissed_at,
                "on_since": self.on_since}

    @callback
    def _save(self) -> None:
        self._store.async_delay_save(self._data, 5)

    async def async_set_definitions(self, pills: list[dict[str, Any]], groups: list[str]) -> None:
        self.pills, self.groups = pills, groups
        keys = {p["key"] for p in pills}
        self.dismissed_at = {k: v for k, v in self.dismissed_at.items() if k in keys}
        self.on_since = {k: v for k, v in self.on_since.items() if k in keys}
        await self._store.async_save(self._data())

    async def async_flush(self) -> None:
        await self._store.async_save(self._data())

    async def async_remove_store(self) -> None:
        await self._store.async_remove()

    # ── options ──────────────────────────────────────────────────────────────
    @property
    def places(self) -> int:
        return int(self.entry.options.get(CONF_PLACES, DEFAULT_PLACES))

    @property
    def card_only(self) -> set[str]:
        return set(self.entry.options.get(CONF_CARD_ONLY, []))

    def is_enabled(self, key: str) -> bool:
        return logic.enabled(self.by_key[key], self.entry.options.get(CONF_DISABLED, []),
                             self.entry.options.get(CONF_DISABLED_GROUPS, []))

    def is_dismissed(self, key: str) -> bool:
        return logic.dismissed(self.on_since.get(key), self.dismissed_at.get(key))

    # ── evaluation ───────────────────────────────────────────────────────────
    @callback
    def async_start(self) -> None:
        """Track the templates of every enabled pill."""
        self.async_stop()
        for pill in self.pills:
            key = pill["key"]
            self.states[key] = PillState()
            if not self.is_enabled(key):
                self._was_on.discard(key)
                self.on_since.pop(key, None)
                continue
            templates = [TrackTemplate(Template(pill["state"], self.hass), None),
                         TrackTemplate(Template(pill["color"], self.hass), None)]
            if pill.get("content"):
                templates.append(TrackTemplate(Template(pill["content"], self.hass), None))
            info = async_track_template_result(self.hass, templates, self._results_handler(key, templates))
            info.async_refresh()
            self._trackers.append(info)
        self._recompute(None)

    @callback
    def async_stop(self) -> None:
        for info in self._trackers:
            info.async_remove()
        self._trackers.clear()

    def _results_handler(self, key: str, templates: list[TrackTemplate]):
        state_tpl, color_tpl = templates[0].template, templates[1].template
        content_tpl = templates[2].template if len(templates) > 2 else None

        @callback
        def handle(event: Event | None, updates: list[TrackTemplateResult]) -> None:
            st = self.states[key]
            for update in updates:
                result = update.result
                if update.template is state_tpl:
                    if isinstance(result, TemplateError):
                        if st.error != str(result):
                            _LOGGER.warning("Pill %s: %s", key, result)
                        st.error, on = str(result), False
                    else:
                        st.error, on = None, result_as_boolean(result)
                    self._set_on(key, on)
                    st.on = None if st.error else on
                elif isinstance(result, TemplateError):
                    continue
                elif update.template is color_tpl:
                    st.color = str(result)
                elif update.template is content_tpl:
                    st.content = "" if result is None else str(result)
            self._recompute({key})

        return handle

    def _set_on(self, key: str, on: bool) -> None:
        was = self.on_since.get(key)
        if on and was is None:
            self.on_since[key] = time.time()
        elif on and key in self._was_on:
            pass  # still on from before the restart: keep its on_since
        elif not on and was is not None:
            self.on_since.pop(key)
            self.dismissed_at.pop(key, None)
        self._was_on.discard(key)
        self._save()

    @callback
    def _recompute(self, keys: set[str] | None) -> None:
        self.shown = [p["key"] for p in self.pills
                      if self.states.get(p["key"], PillState()).on and not self.is_dismissed(p["key"])]
        self.row, self.overflow = logic.row(self.shown, self.card_only, self.places)
        for listener in list(self._listeners):
            listener(keys)

    def slots(self) -> list[dict[str, str]]:
        """What the row's chips show, place by place."""
        out = [{"key": k, "icon": self.by_key[k]["icon"], "color": self.states[k].color,
                "content": self.states[k].content} for k in self.row]
        if self.overflow:
            out.append({"key": "", "icon": "", "color": "", "content": f"+{self.overflow}"})
        return out

    # ── listeners ────────────────────────────────────────────────────────────
    @callback
    def async_add_listener(self, listener: Listener) -> CALLBACK_TYPE:
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    @callback
    def async_options_updated(self) -> None:
        """Options changed: re-track (enabled pills may differ) and redraw everything."""
        self.async_start()

    # ── dismissing ───────────────────────────────────────────────────────────
    def dismiss(self, key: str) -> None:
        self.dismissed_at[key] = time.time()
        self._save()
        self._recompute({key})

    def restore(self, key: str) -> None:
        self.dismissed_at.pop(key, None)
        self._save()
        self._recompute({key})

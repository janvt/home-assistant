"""Setting up Alert pills (no questions) and its options, which work from the phone:
Settings → Devices & services → Alert pills → Configure.
"""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_CARD_ONLY,
    CONF_DISABLED,
    CONF_DISABLED_GROUPS,
    CONF_PLACES,
    DEFAULT_PLACES,
    DOMAIN,
    MAX_PLACES,
)


class AlertPillsConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        # Nothing to ask: the pills arrive later through `alert_pills.load`.
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="Alert pills", data={})

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return AlertPillsOptionsFlow()


class AlertPillsOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            user_input[CONF_PLACES] = int(user_input[CONF_PLACES])
            return self.async_create_entry(data=user_input)

        manager = self.config_entry.runtime_data
        options = self.config_entry.options
        pills = [SelectOptionDict(value=p["key"], label=f"{p['name']} · {p['group']}") for p in manager.pills]
        keys = {p["key"] for p in manager.pills}
        groups = manager.groups or sorted({p["group"] for p in manager.pills})

        def known(name: str, valid: set[str] | list[str]) -> list[str]:
            # Pills or groups removed from pills.py since they were picked.
            return [k for k in options.get(name, []) if k in valid]

        schema = vol.Schema({
            vol.Optional(CONF_DISABLED, default=known(CONF_DISABLED, keys)): SelectSelector(
                SelectSelectorConfig(options=pills, multiple=True, mode=SelectSelectorMode.DROPDOWN)),
            vol.Optional(CONF_DISABLED_GROUPS, default=known(CONF_DISABLED_GROUPS, groups)): SelectSelector(
                SelectSelectorConfig(options=groups, multiple=True, mode=SelectSelectorMode.LIST)),
            vol.Optional(CONF_CARD_ONLY, default=known(CONF_CARD_ONLY, keys)): SelectSelector(
                SelectSelectorConfig(options=pills, multiple=True, mode=SelectSelectorMode.DROPDOWN)),
            vol.Required(CONF_PLACES, default=options.get(CONF_PLACES, DEFAULT_PLACES)): NumberSelector(
                NumberSelectorConfig(min=1, max=MAX_PLACES, step=1, mode=NumberSelectorMode.SLIDER)),
        })
        return self.async_show_form(step_id="init", data_schema=schema,
                                    description_placeholders={"count": str(len(manager.pills))})

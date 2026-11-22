"""Setup of Andermatt Live: the sectors to follow."""

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from custom_components.andermatt_live.const import CONF_SECTORS, DOMAIN, USER_AGENT
from custom_components.andermatt_live.live import (
    BASE_URL,
    SECTORS,
    AndermattLiveClient,
    AndermattLiveError,
)

# Gemsstock is the one most people come for.
DEFAULT_SECTORS = ["gemsstock", "andermatt-oberalppass"]


def schema(selected: list[str]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_SECTORS, default=selected): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(value=slug, label=name)
                        for slug, name in SECTORS.items()
                    ],
                    multiple=True,
                    mode=SelectSelectorMode.LIST,
                )
            ),
        }
    )


class AndermattLiveFlowHandler(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return AndermattLiveOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors = {}
        selected = DEFAULT_SECTORS
        if user_input is not None:
            selected = user_input[CONF_SECTORS]
            if not selected:
                errors[CONF_SECTORS] = "no_sectors"
            else:
                # One sector read now: the site answers, and the pages are
                # still the ones this integration knows how to read.
                client = AndermattLiveClient(
                    async_get_clientsession(self.hass), USER_AGENT
                )
                try:
                    await client.async_sector(selected[0])
                except AndermattLiveError:
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(
                        title="Andermatt+Sedrun+Disentis", data=user_input
                    )
        return self.async_show_form(
            step_id="user",
            data_schema=schema(selected),
            errors=errors,
            # Home Assistant does not allow links in the translations.
            description_placeholders={"site": f"[A+S+D Live Dashboard]({BASE_URL})"},
        )


class AndermattLiveOptionsFlow(OptionsFlow):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        current = {**self.config_entry.data, **self.config_entry.options}
        errors = {}
        if user_input is not None:
            if user_input[CONF_SECTORS]:
                # Reloads the entry (see update_listener).
                return self.async_create_entry(data=user_input)
            errors[CONF_SECTORS] = "no_sectors"
        return self.async_show_form(
            step_id="init",
            data_schema=schema([s for s in current[CONF_SECTORS] if s in SECTORS]),
            errors=errors,
        )

"""Config flow for Reef Factory KH Keeper."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant

from .const import CONF_EMAIL, CONF_PASSWORD, CONF_SERIAL, DOMAIN
from .coordinator import async_validate_credentials

_LOGGER = logging.getLogger(__name__)

STEP_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_SERIAL): str,
    }
)


class ReefFactoryKHConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Reef Factory KH Keeper."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            password = user_input[CONF_PASSWORD]
            serial = user_input[CONF_SERIAL].strip()

            await self.async_set_unique_id(serial)
            self._abort_if_unique_id_configured()

            try:
                valid = await asyncio.wait_for(
                    async_validate_credentials(self.hass, email, password),
                    timeout=20,
                )
                if valid:
                    return self.async_create_entry(
                        title=f"KH Keeper {serial}",
                        data={
                            CONF_EMAIL: email,
                            CONF_PASSWORD: password,
                            CONF_SERIAL: serial,
                        },
                    )
                errors["base"] = "invalid_auth"
            except asyncio.TimeoutError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during config flow")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "serial_hint": "Find the serial number in the Smart Reef app under device settings"
            },
        )

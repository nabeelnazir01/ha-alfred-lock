"""Config flow for Alfred Smart Lock integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .alfred_api import AlfredApiClient, AlfredAuthError, AlfredApiError
from .const import CONF_ACCOUNT, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate user credentials against Alfred Cloud."""
    session = async_get_clientsession(hass)
    account = data[CONF_USERNAME].strip().lower()
    password = data[CONF_PASSWORD]

    client = AlfredApiClient(account=account, password=password, session=session)

    try:
        tokens = await client.login()
        devices = await client.get_devices()
    except AlfredAuthError as err:
        raise InvalidAuth from err
    except (AlfredApiError, Exception) as err:
        raise CannotConnect from err

    locks = [d for d in devices if d.get("isLock")]
    _LOGGER.info("Authenticated %s, discovered %d lock(s)", account, len(locks))

    return {
        "title": account,
        "tokens": tokens,
        "devices": devices,
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Alfred Smart Lock."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            account = user_input[CONF_USERNAME].strip().lower()
            await self.async_set_unique_id(account)
            self._abort_if_unique_id_configured()

            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception during Alfred setup")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=info["title"],
                    data={
                        CONF_ACCOUNT: account,
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        "tokens": info["tokens"],
                        "devices": info["devices"],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuth(Exception):
    """Error to indicate there is invalid auth."""

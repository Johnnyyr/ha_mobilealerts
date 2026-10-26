"""Config flow for MobileAlerts."""

from __future__ import annotations

from typing import Any

import asyncio
import logging
import socket

import voluptuous as vol
from homeassistant.components import dhcp, onboarding
from homeassistant.components.network import async_get_source_ip
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from mobilealerts import Gateway

from .const import (
    CONF_GATEWAY,
    CONF_GATEWAY_IP,
    CONF_PROXY_PORT,
    DEFAULT_PROXY_PORT,
    CONF_MODE,
    CONF_MQTT_TOPIC_PREFIX,
    CONF_SEND_DATA_TO_CLOUD,
    DEFAULT_MQTT_TOPIC_PREFIX,
    DOMAIN,
    MODE_ENTITIES,
    MODE_MQTT,
)
from .util import gateway_full_name, gateway_short_name

_LOGGER = logging.getLogger(__name__)


class MobileAlertsOptionsFlowHandler(OptionsFlow):
    """Handle a MobileAlerts options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        return await self.async_step_proxy(user_input)

    async def async_step_proxy(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle options flow."""
        if user_input is not None:
            host = user_input.get(CONF_GATEWAY_IP)
            if host:
                try:
                    Gateway.validate_gateway_ip(host)
                except ValueError:
                    return self.async_show_form(
                        step_id="proxy",
                        data_schema=self._schema(user_input),
                        errors={CONF_GATEWAY_IP: "invalid_host"},
                    )
                local_ip = await async_get_source_ip(self.hass, host)
                try:
                    gateways = await Gateway.discover(local_ip, gateway_ip=host)
                except (OSError, asyncio.TimeoutError):
                    gateways = []
                if not any(
                    g.gateway_id == self.config_entry.unique_id for g in gateways
                ):
                    return self.async_show_form(
                        step_id="proxy",
                        data_schema=self._schema(user_input),
                        errors={"base": "cannot_connect"},
                    )
            return self.async_create_entry(title="", data=user_input)

        options = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(step_id="proxy", data_schema=self._schema(options))

    def _schema(self, options: dict[str, Any]) -> vol.Schema:
        return vol.Schema(
            {
                vol.Optional(
                    CONF_GATEWAY_IP, default=options.get(CONF_GATEWAY_IP, "")
                ): str,
                vol.Required(
                    CONF_PROXY_PORT, default=options.get(CONF_PROXY_PORT, 0)
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=65535)),
                vol.Required(
                    CONF_MODE,
                    default=options.get(CONF_MODE, MODE_ENTITIES),
                ): vol.In(
                    {
                        MODE_ENTITIES: "Native Home Assistant entities",
                        MODE_MQTT: "MQTT gateway (sarnau-compatible)",
                    }
                ),
                vol.Required(
                    CONF_SEND_DATA_TO_CLOUD,
                    default=options.get(CONF_SEND_DATA_TO_CLOUD, True),
                ): bool,
                vol.Optional(
                    CONF_MQTT_TOPIC_PREFIX,
                    default=options.get(
                        CONF_MQTT_TOPIC_PREFIX, DEFAULT_MQTT_TOPIC_PREFIX
                    ),
                ): str,
            }
        )


class MobileAlertsConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a MobileAlerts config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._gateway: Gateway | None = None
        self._gateways: dict[str, Gateway] = {}

    async def async_step_single_gateway(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure the gateway."""
        gateway = self._gateway
        assert gateway is not None
        _LOGGER.debug("async_step_single_gateway gateway %s", gateway)

        if user_input is not None or not onboarding.async_is_onboarded(self.hass):
            await self.async_set_unique_id(gateway.gateway_id, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=gateway_short_name(gateway),
                data=user_input,
            )

        return self.async_show_form(
            step_id="single_gateway",
            description_placeholders={"name": gateway_full_name(gateway)},
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SEND_DATA_TO_CLOUD,
                        default=True,
                    ): bool,
                }
            ),
        )

    async def async_step_multiple_gateways(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select a gateway."""

        if user_input is not None:
            assert self._gateways is not None
            gateway_id = user_input[CONF_GATEWAY]
            await self.async_set_unique_id(gateway_id, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            gateway = self._gateways[gateway_id]
            return self.async_create_entry(
                title=gateway_short_name(gateway),
                data={},
            )

        configured_gateways = self._async_current_ids()

        gateways = []
        ip_address = await async_get_source_ip(self.hass)
        try:
            gateways = await Gateway.discover(ip_address)
        except socket.error as err:
            _LOGGER.error("Gateways discovery error %r", err)

        if len(gateways) == 0:
            return self.async_abort(reason="no_devices_found")

        self._gateways = {gateway.gateway_id: gateway for gateway in gateways}

        unconfigured_gateways = [
            gateway
            for gateway in gateways
            if gateway.gateway_id not in configured_gateways
        ]

        if not unconfigured_gateways:
            return self.async_abort(reason="no_gateways")

        if len(unconfigured_gateways) == 1:
            self._gateway = unconfigured_gateways[0]
            return await self.async_step_single_gateway()

        return self.async_show_form(
            step_id="multiple_gateways",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_GATEWAY): vol.In(
                        {
                            gateway.gateway_id: gateway_short_name(gateway)
                            for gateway in unconfigured_gateways
                        }
                    ),
                }
            ),
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        return self.async_show_menu(
            step_id="user", menu_options=["automatic", "manual"]
        )

    async def async_step_automatic(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Keep existing local broadcast discovery."""
        return await self.async_step_multiple_gateways(user_input)

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Probe one gateway by IPv4 address, including across routed VLANs."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_GATEWAY_IP].strip()
            try:
                host = Gateway.validate_gateway_ip(host)
            except ValueError:
                errors[CONF_GATEWAY_IP] = "invalid_host"
            if not errors:
                try:
                    local_ip = await async_get_source_ip(self.hass, host)
                    gateways = await Gateway.discover(local_ip, gateway_ip=host)
                except (OSError, asyncio.TimeoutError):
                    gateways = []
                if gateways:
                    gateway = gateways[0]
                    await self.async_set_unique_id(gateway.gateway_id)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=gateway_short_name(gateway),
                        data={**user_input, CONF_GATEWAY_IP: host},
                    )
                errors["base"] = "cannot_connect"
        values = user_input or {}
        return self.async_show_form(
            step_id="manual",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_GATEWAY_IP, default=values.get(CONF_GATEWAY_IP, "")
                    ): str,
                    vol.Required(
                        CONF_PROXY_PORT,
                        default=values.get(CONF_PROXY_PORT, DEFAULT_PROXY_PORT),
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=65535)),
                    vol.Required(
                        CONF_SEND_DATA_TO_CLOUD,
                        default=values.get(CONF_SEND_DATA_TO_CLOUD, False),
                    ): bool,
                }
            ),
        )

    async def async_step_dhcp(self, discovery_info: dhcp.DhcpServiceInfo) -> FlowResult:
        """Handle a flow initialized by DHCP discovery."""
        _LOGGER.debug("async_step_dhcp %s", discovery_info)

        gateway_id = discovery_info.macaddress.upper().replace(":", "")
        await self.async_set_unique_id(gateway_id)
        self._abort_if_unique_id_configured()

        gateway = Gateway(gateway_id)
        try:
            if not await gateway.init():
                return self.async_abort(reason="unknown")
        except socket.error as err:
            _LOGGER.error("Gateways initialization error %r", err)
            return self.async_abort(reason="unknown")

        self._gateway = gateway
        self.context["title_placeholders"] = {"name": gateway_full_name(gateway)}
        return await self.async_step_single_gateway()

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> MobileAlertsOptionsFlowHandler:
        """Get the options flow for this handler."""
        return MobileAlertsOptionsFlowHandler()

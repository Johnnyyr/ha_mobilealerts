"""Exercise config flows and setup with real Home Assistant classes."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
import pytest_asyncio
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntries
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.data_entry_flow import AbortFlow
from mobilealerts import Gateway

from custom_components.mobile_alerts import async_setup_entry
from custom_components.mobile_alerts.config_flow import MobileAlertsConfigFlowHandler

HOST = "192.0.2.81"
MAC = "001D8C0DF7E1"


@pytest_asyncio.fixture
async def hass(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    hass.config_entries = ConfigEntries(hass, {})
    return hass


def flow_for(hass):
    flow = MobileAlertsConfigFlowHandler()
    flow.hass = hass
    flow.handler = "mobile_alerts"
    flow.context = {"source": "user"}
    flow.flow_id = "test"
    return flow


@pytest.mark.asyncio
async def test_user_can_choose_manual_or_automatic(hass):
    result = await flow_for(hass).async_step_user()
    assert result["type"] == "menu"
    assert set(result["menu_options"]) == {"automatic", "manual"}


@pytest.mark.asyncio
async def test_manual_entry_persists_host_and_port_with_mac_identity(hass):
    flow = flow_for(hass)
    gateway = Mock(gateway_id=MAC)
    with patch(
        "custom_components.mobile_alerts.config_flow.Gateway.discover",
        AsyncMock(return_value=[gateway]),
    ), patch(
        "custom_components.mobile_alerts.config_flow.async_get_source_ip",
        AsyncMock(return_value="192.0.2.102"),
    ):
        result = await flow.async_step_manual(
            {"gateway_ip": HOST, "proxy_port": 8088, "send_data_to_cloud": False}
        )
    assert result["type"] == "create_entry"
    assert result["data"] == {
        "gateway_ip": HOST,
        "proxy_port": 8088,
        "send_data_to_cloud": False,
    }
    assert flow.context["unique_id"] == MAC


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "host", ["bad", "::1", "255.255.255.255", "224.0.0.1", "0.0.0.0"]
)
async def test_bad_manual_host_is_recoverable(hass, host):
    result = await flow_for(hass).async_step_manual(
        {"gateway_ip": host, "proxy_port": 8088, "send_data_to_cloud": False}
    )
    assert result["type"] == "form"
    assert result["errors"]["gateway_ip"] == "invalid_host"


@pytest.mark.asyncio
async def test_unreachable_manual_host_shows_error(hass):
    with patch(
        "custom_components.mobile_alerts.config_flow.Gateway.discover",
        AsyncMock(return_value=[]),
    ), patch(
        "custom_components.mobile_alerts.config_flow.async_get_source_ip",
        AsyncMock(return_value="192.0.2.102"),
    ):
        result = await flow_for(hass).async_step_manual(
            {"gateway_ip": HOST, "proxy_port": 8088, "send_data_to_cloud": False}
        )
    assert result["errors"]["base"] == "cannot_connect"


@pytest.mark.asyncio
async def test_duplicate_mac_is_rejected_even_for_new_ip(hass):
    flow = flow_for(hass)
    gateway = Mock(gateway_id=MAC)
    with patch(
        "custom_components.mobile_alerts.config_flow.Gateway.discover",
        AsyncMock(return_value=[gateway]),
    ), patch(
        "custom_components.mobile_alerts.config_flow.async_get_source_ip",
        AsyncMock(return_value="192.0.2.102"),
    ), patch.object(
        hass.config_entries,
        "async_entry_for_domain_unique_id",
        return_value=SimpleNamespace(
            unique_id=MAC, entry_id="existing", source="user", data={}
        ),
    ):
        with pytest.raises(AbortFlow, match="already_configured"):
            await flow.async_step_manual(
                {"gateway_ip": HOST, "proxy_port": 8088, "send_data_to_cloud": False}
            )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "data,options,host,port,cloud",
    [
        (
            {"gateway_ip": HOST, "proxy_port": 8088, "send_data_to_cloud": False},
            {},
            HOST,
            8088,
            False,
        ),
        ({}, {}, None, 0, True),
        (
            {"gateway_ip": HOST, "proxy_port": 8088},
            {"gateway_ip": "192.0.2.82", "proxy_port": 8089},
            "192.0.2.82",
            8089,
            True,
        ),
    ],
)
async def test_setup_restores_manual_and_legacy_transport(
    hass, data, options, host, port, cloud
):
    entry = SimpleNamespace(
        as_dict=lambda: {},
        unique_id=MAC,
        data=data,
        options=options,
        entry_id="entry",
        async_on_unload=Mock(),
        add_update_listener=Mock(),
    )
    gateway = Mock(ip_address=host or HOST, init=AsyncMock(return_value=True))
    proxy = Mock(start=AsyncMock(), stop=AsyncMock())
    coordinator = SimpleNamespace(async_get_or_create_gateway_device=AsyncMock())
    with patch(
        "custom_components.mobile_alerts.Gateway", return_value=gateway
    ) as constructor, patch(
        "custom_components.mobile_alerts.Proxy", return_value=proxy
    ) as proxy_constructor, patch(
        "custom_components.mobile_alerts.async_get_source_ip",
        AsyncMock(return_value="192.0.2.102"),
    ), patch(
        "custom_components.mobile_alerts.MobileAlertesDataCoordinator",
        return_value=coordinator,
    ), patch(
        "custom_components.mobile_alerts.dr.async_get", return_value=Mock()
    ), patch(
        "custom_components.mobile_alerts.dr.async_entries_for_config_entry",
        return_value=[],
    ), patch.object(
        hass.config_entries, "async_forward_entry_setups", AsyncMock()
    ):
        assert await async_setup_entry(hass, entry)
    assert constructor.call_args.kwargs["gateway_ip"] == host
    assert proxy_constructor.call_args.args == (None, "192.0.2.102", port)
    assert gateway.send_data_to_cloud == cloud


@pytest.mark.asyncio
async def test_busy_proxy_port_retries_without_attaching_gateway(hass):
    entry = SimpleNamespace(
        as_dict=lambda: {},
        unique_id=MAC,
        data={"gateway_ip": HOST, "proxy_port": 8088},
        options={},
        entry_id="entry",
    )
    gateway = Mock(ip_address=HOST, init=AsyncMock(return_value=True))
    proxy = Mock(
        start=AsyncMock(side_effect=OSError("Address already in use")), stop=AsyncMock()
    )
    with patch("custom_components.mobile_alerts.Gateway", return_value=gateway), patch(
        "custom_components.mobile_alerts.Proxy", return_value=proxy
    ), patch(
        "custom_components.mobile_alerts.async_get_source_ip",
        AsyncMock(return_value="192.0.2.102"),
    ), patch(
        "custom_components.mobile_alerts.MobileAlertesDataCoordinator",
        return_value=Mock(),
    ):
        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, entry)
    proxy.attach_gateway.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("reply_mac,accepted", [(MAC, True), ("001D8CFFFFFF", False)])
async def test_options_ip_change_must_keep_gateway_identity(hass, reply_mac, accepted):
    from custom_components.mobile_alerts.config_flow import (
        MobileAlertsOptionsFlowHandler,
    )

    flow = MobileAlertsOptionsFlowHandler()
    flow.hass = hass
    flow.handler = "entry"
    flow.flow_id = "options"
    entry = SimpleNamespace(unique_id=MAC, data={"gateway_ip": HOST}, options={})
    values = {
        "gateway_ip": "192.0.2.82",
        "proxy_port": 8089,
        "send_data_to_cloud": False,
    }
    with patch.object(
        hass.config_entries, "async_get_known_entry", return_value=entry
    ), patch(
        "custom_components.mobile_alerts.config_flow.async_get_source_ip",
        AsyncMock(return_value="192.0.2.102"),
    ), patch(
        "custom_components.mobile_alerts.config_flow.Gateway.discover",
        AsyncMock(return_value=[Mock(gateway_id=reply_mac)]),
    ):
        result = await flow.async_step_proxy(values)
    if accepted:
        assert result["type"] == "create_entry"
        assert result["data"] == values
    else:
        assert result["errors"]["base"] == "cannot_connect"


@pytest.mark.asyncio
@pytest.mark.parametrize("port", [-1, 65536])
async def test_proxy_port_form_rejects_out_of_range_values(hass, port):
    import voluptuous as vol

    result = await flow_for(hass).async_step_manual()
    with pytest.raises(vol.Invalid):
        result["data_schema"](
            {"gateway_ip": HOST, "proxy_port": port, "send_data_to_cloud": False}
        )

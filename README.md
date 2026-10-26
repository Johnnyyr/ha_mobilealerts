# Home Assistant support for Mobile-Alerts

## About this fork

This is [Johnnyyr/ha_mobilealerts](https://github.com/Johnnyyr/ha_mobilealerts),
a fork of [m-l/ha_mobilealerts](https://github.com/m-l/ha_mobilealerts), which is
based on [PlusPlus-ua/ha_mobilealerts](https://github.com/PlusPlus-ua/ha_mobilealerts).
Original credits and MIT copyright/license notices are preserved. This fork adds
manual IPv4 setup across routed VLANs, a configurable proxy port, and German setup
translations. It uses the companion [Johnnyyr/python-mobilealerts](https://github.com/Johnnyyr/python-mobilealerts)
fork, pinned to an immutable commit rather than a moving branch or a PyPI release.

Repository names, HA integration domain (`mobile_alerts`) and Python import name
(`mobilealerts`) stay unchanged. Install only one fork of this HA integration at a
time: forks share the same integration domain and cannot be installed side by side.
No mobile app, cloud account or MQTT broker is needed in native-entities mode.
The upstream library may still attempt an optional cloud lookup of a new sensor's
name; forwarding measurements can be disabled independently. A local default name
is used when that lookup fails.

## Installing this fork with HACS

1. In HACS, open **Custom repositories** and add
   `https://github.com/Johnnyyr/ha_mobilealerts` as an **Integration**.
2. Download this fork and restart Home Assistant. If another Mobile-Alerts fork
   is already installed, back up its configuration and replace its HACS source
   rather than installing both. Existing devices use the same domain and MAC IDs.
3. Open **Settings → Devices & services → Add integration → Mobile-Alerts**.
4. Choose **Enter gateway IP**, enter the gateway IPv4 address, and choose a free
   proxy TCP port (for example `8088`). Disable cloud forwarding for local operation.
5. Keep native entities selected. The gateway is identified by its MAC; sensors
   appear after their next transmission. For a rain gauge, trigger the rocker
   once to test reception; dry periods may have long reporting intervals.

The fork's dependency is installed automatically by HA. Do not replace it with
`pip install mobilealerts` from PyPI: that release lacks the unicast argument.
The first installation/update needs outbound HTTPS to GitHub for the dependency
archive. No custom `configuration.yaml` entries or MQTT installation are required.

## Routed VLANs and firewall

The manual path uses directed UDP, so the gateway can remain in another subnet.
Automatic discovery still requires the local broadcast domain. Reserve the
gateway's IPv4 address through DHCP. On **Configure**, its IP can be updated
without recreating devices; the replacement IP must answer with the same MAC.
An empty address switches back to broadcast control. The proxy port is editable;
`0` keeps the legacy automatic port and is unsuitable for narrow static rules.
Each gateway requires its own free fixed TCP port.

For example, with HA `192.168.1.100`, gateway `192.168.2.100`, and proxy TCP `8088`:

| Source | Destination | Protocol / destination port | Purpose |
| --- | --- | --- | --- |
| `192.168.1.100` | `192.168.2.100` | UDP `8003` | Discovery, configuration and refresh |
| `192.168.2.100` | `192.168.1.100` | TCP `8088` | Gateway uploads to the HA proxy |

Allow stateful replies, place these host-specific exceptions before the relevant
inter-VLAN deny rule, and retain normal DHCP service for the gateway. No mDNS relay,
broadcast forwarding or Internet port forwarding is needed. These are example
rules, not changes automatically made by this integration. An occupied port causes
setup to retry without redirecting the gateway to an unusable listener.

### Replacing an existing Matrix / maserver proxy

The gateway has one active proxy destination. Before enabling this integration:
record the previous proxy IP/port, stop and disable the old proxy service's automatic
configuration, then configure the HA integration. Otherwise the two controllers can
keep overwriting each other's gateway settings. For Cypher Matrix this is the
`cypher-mobile-alerts.service` on the Pi; disable its automatic start as part of a
planned handover. This repository does not change that service or the firewall.
Matrix will stop receiving new gateway measurements unless a separate HA-to-Matrix
feed is implemented. Existing saved Matrix measurements are not deleted.

For rollback, unload/remove the HA integration first, then restore the recorded
proxy destination and re-enable the previous service. Changing proxy settings does
not establish that a sensor is transmitting: verify a fresh timestamp and rain
counter change from a physical rocker event.

## Development verification

Clone the companion library as a sibling directory named `python-mobilealerts`,
then use Python 3.14 (matching HA 2026.10):

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements_test.txt
.venv/bin/python -m pytest -q tests
python3 .github/scripts/check_changelog.py
```

Tests use real Home Assistant config-flow classes and replace external network and
registry boundaries. They do not modify a running HA installation or gateway.

## Fork maintenance and contributions

`origin` is your Johnnyyr fork; `upstream` points to the project it was forked from.
Work on a feature branch, test it, and push it to your fork. A pull request proposes
merging that branch into another branch/repository; it does not change upstream
until its maintainers merge it. There are two codebases: this HA UI/entity integration
and the reusable transport library. Submit transport changes to the library first,
then update the HA dependency after a compatible upstream release is available.
Maintainer messages and upstream PRs are not submitted automatically by this fork.

The LICENSE files retain the original copyright and permission notice. The origin
links above and existing Credits make the lineage visible; renaming is unnecessary.

## Overview

This integration supports various Mobile-Alerts sensors. The integration acts as proxy server between Mobile-Alerts gateway and cloud. 

Readings can be exposed either as **native Home Assistant entities** or through an **MQTT gateway** mode that republishes them in the sarnau/MMMMobileAlerts JSON format, so an existing `mqtt:` sensor configuration (or a standalone maserver setup) keeps working unchanged.

_Based on MMMMobileAlerts by [@sarnau](https://github.com/sarnau/MMMMobileAlerts)

## Installation

Place the `custom_components` folder in your configuration directory (or add its contents to an existing `custom_components` folder). Alternatively install via [HACS](https://hacs.xyz/).

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=m-l&repository=ha_mobilealerts&category=integration)

## Configuration

The gateway is discovered automatically (UDP broadcast and DHCP). Add the integration from **Settings → Devices & Services → Add Integration → Mobile-Alerts**. Home Assistant and the gateway must be on the same subnet for discovery to succeed.

Once added, open the integration's **Configure** dialog to choose how readings are exposed and whether data is still forwarded to the Mobile-Alerts cloud. Changes are applied immediately (the config entry reloads automatically).

### Modes

**Native Home Assistant entities** (default) — each measurement becomes a Home Assistant `sensor` / `binary_sensor` entity. Temperature, humidity, CO2, air pressure, wind speed and gust sensors have state class `measurement`, and rain totals `total_increasing`, so Home Assistant keeps long-term statistics for them.

> **Coming from another fork?** Before version 0.3.11 these sensors had no state class. If you previously ran a fork that did set one (for example Iminet72/ha_mobilealerts), Home Assistant may show the repair notice "we have generated statistics in the past, but it no longer has a state class". Update to 0.3.11 or later and restart. Do **not** press the button that deletes the long-term statistics: with the state class back, the entity keeps recording under the same entity id and its existing history is kept.

**MQTT gateway (sarnau-compatible)** — each sensor's readings are published as a single JSON document to:

```
<mqtt_topic_prefix><sensor_id>/json
```

The topic prefix defaults to `/MobileAlerts/` and `<sensor_id>` is lower-case, matching the topic layout of [MMMMobileAlerts](https://github.com/sarnau/MMMMobileAlerts) / maserver. This lets the integration replace a standalone maserver while your existing `mqtt:` sensors continue to work.

The broker connection is **not** configured here — messages are published through Home Assistant's own MQTT integration, so the broker host, port and credentials live there. The MQTT integration must be set up for this mode to work.

#### Payload

Environmental measurements are published as **arrays** (templates read index `0`); wind values and all metadata are **scalars**. Each message also carries per-sensor metadata:

```json
{
  "temperature": [21.3],
  "humidity": [55],
  "temperatureExt": [12.1],
  "windSpeed": 0.2,
  "gustSpeed": 1.0,
  "directionDegree": 90,
  "direction": "E",
  "battery": "ok",
  "offline": false,
  "id": "094596df5368",
  "t": "2022-09-15T06:27:50.000Z",
  "lastTransmit": 360,
  "by_event": false,
  "counter": 54242,
  "model": "MA10238",
  "name": "Air pressure monitor (...)"
}
```

| Key | Type | Notes |
| --- | --- | --- |
| `temperature`, `temperatureExt`, `humidity`, `airPressure`, `co2`, `rain` | array | Index `0` is the current value. `temperatureExt` is a second/external probe (pool, water). |
| `windSpeed`, `gustSpeed` | scalar | m/s |
| `directionDegree` | scalar | Wind direction in degrees |
| `direction` | scalar | 16-point compass string (`N`, `NNE`, ...) |
| `wetness`, `contact` | scalar | Leakage / door-window sensors |
| `eventCounter` | scalar | Rain sensors: cumulative bucket-tip counter |
| `eventTimes` | array | Rain sensors: seconds since each of the last 9 events (`[0]` is the most recent; `0` = an event in this transmission) |
| `battery` | scalar | `"ok"` or `"low"` |
| `t` | scalar | Reading time, ISO 8601 UTC |
| `lastTransmit` | scalar | Sensor transmit interval, seconds |
| `id` | scalar | Sensor id (also in the topic) |
| `by_event` | scalar | `true` if triggered by an event rather than a scheduled report |
| `counter` | scalar | Packet counter |
| `offline` | scalar | Always `false` — see note below |
| `model`, `name` | scalar | Sensor model / name |

> **`offline`:** the integration publishes only when a sensor transmits, so `offline` is always `false` (there is no watchdog that flips it to `true` after silence — use the age of `t` for staleness instead). Rain sensors additionally publish `eventCounter` and `eventTimes`, parsed directly from the packet, so rain-gauge templates that count bucket tips work as they did with maserver.

> **Missing keys:** not every model reports every key — for example `lastTransmit` is absent on the MA10230 Humidity Guard. In templates that must tolerate this, read keys with `value_json.get('key')` instead of `value_json.key`; an absent key makes `tojson` fail with "Object of type Undefined is not JSON serializable" (this matters in `json_attributes_template`).

Example `mqtt:` sensor reusing the published data:

```yaml
mqtt:
  sensor:
    - state_topic: "/MobileAlerts/094596df5368/json"
      name: "Garage Temperature"
      value_template: "{{ value_json.temperature[0] | float }}"
      unit_of_measurement: "°C"
    - state_topic: "/MobileAlerts/094596df5368/json"
      name: "Garage Humidity"
      value_template: "{{ value_json.humidity[0] | float }}"
      unit_of_measurement: "%"
```

Battery status as a binary sensor:

```yaml
mqtt:
  binary_sensor:
    - state_topic: "/MobileAlerts/094596df5368/json"
      name: "Garage sensor battery"
      device_class: battery
      value_template: "{{ 'ON' if value_json.battery == 'low' else 'OFF' }}"
```

#### Rain sensor example

Rain sensors publish `eventCounter` (bucket tips counted by the sensor), `eventTimes` (age of the last 9 tips) and the cumulative `rain` value in mm, alongside the usual `temperature`. A rain sensor transmits when its bucket tips and otherwise only rarely — `lastTransmit` reports 7200 s (2 h) on an MA10650 — so don't give its entities a short `expire_after`, or they will go unavailable during every dry spell.

```yaml
mqtt:
  sensor:
    # Cumulative rainfall in mm, as computed by the integration (0.25 mm per tip)
    - name: "Rain total"
      state_topic: "/MobileAlerts/083b2e19ccc9/json"
      unit_of_measurement: "mm"
      device_class: precipitation
      state_class: total_increasing
      value_template: "{{ value_json.rain[0] | float }}"

    # The same from the tip counter, with your own calibration (mm per tip)
    - name: "Rain total calibrated"
      state_topic: "/MobileAlerts/083b2e19ccc9/json"
      unit_of_measurement: "mm"
      device_class: precipitation
      state_class: total_increasing
      value_template: "{{ (value_json.eventCounter | int * 0.2495) | round(2) }}"

    # When it last rained: reading time minus the age of the most recent tip
    - name: "Rain last tip"
      state_topic: "/MobileAlerts/083b2e19ccc9/json"
      device_class: timestamp
      value_template: >-
        {{ (as_datetime(value_json.t) - timedelta(seconds=value_json.eventTimes[0] | int)).isoformat() }}

  binary_sensor:
    # ON when the latest transmission contains a fresh tip (eventTimes[0] == 0),
    # back to OFF after 10 minutes without another one
    - name: "Rain tip"
      state_topic: "/MobileAlerts/083b2e19ccc9/json"
      value_template: "{{ 'ON' if value_json.eventTimes[0] | int == 0 else 'OFF' }}"
      off_delay: 600
```

Daily and hourly totals come from Home Assistant's built-in [utility meter](https://www.home-assistant.io/integrations/utility_meter/):

```yaml
utility_meter:
  rain_today:
    source: sensor.rain_total_calibrated
    cycle: daily
  rain_this_hour:
    source: sensor.rain_total_calibrated
    cycle: hourly
```

Things worth knowing:

- `rain` assumes a fixed 0.25 mm per tip. Multiply `eventCounter` by your own value (the example uses 0.2495) if you have calibrated your gauge.
- `eventTimes` stores older events in coarser units (days, hours, minutes), so "Rain last tip" is exact for a fresh tip and approximate for an old one.
- The integration drops a packet whose transmit `counter` it has already published, as maserver did, so a packet delivered twice by the gateway is not counted twice.

### Send data to cloud

When enabled (default), the integration forwards received data to the Mobile-Alerts cloud so the official app keeps working. Disable it to keep everything local.

## Credits

- Protocol and JSON format: [MMMMobileAlerts](https://github.com/sarnau/MMMMobileAlerts) by [@sarnau](https://github.com/sarnau)
- Original Home Assistant integration: [@PlusPlus-ua](https://github.com/PlusPlus-ua/ha_mobilealerts)
- Home Assistant 2024.x compatibility: [@greiter](https://github.com/greiter), [@Silver-Volt4](https://github.com/Silver-Volt4), [@msvb04](https://github.com/msvb04)
- This fork (MQTT gateway mode with the sarnau-compatible payload, rain event decoding, and the fixes listed in the changelog): [@m-l](https://github.com/m-l)


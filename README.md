# Reef Factory KH Keeper — Home Assistant Integration

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/realiztw/reef-factory-kh.svg)](https://github.com/realiztw/reef-factory-kh/releases)
[![Validate](https://github.com/realiztw/reef-factory-kh/actions/workflows/validate.yaml/badge.svg)](https://github.com/realiztw/reef-factory-kh/actions/workflows/validate.yaml)

A Home Assistant custom integration for the **Reef Factory KH Keeper Plus** — an automated alkalinity (KH) testing and monitoring device for reef aquariums.

This integration connects to the [Smart Reef](https://smartreef.reeffactory.com/) cloud API to surface your KH Keeper's readings directly in Home Assistant, enabling automations, dashboards, and long-term history tracking.

---

## Features

- **KH measurement** — latest carbonate hardness reading in dKH
- **Reagent remaining** — how much reagent is left in the reservoir (mL)
- **Last measurement timestamp** — when the last automated test was run
- **KH alarm thresholds** — low and high alarm setpoints (disabled by default, enable via entity settings)
- Polling every 30 minutes via the Smart Reef WebSocket API
- Full UI-based setup — no YAML configuration required

---

## Prerequisites

- A [Reef Factory KH Keeper Plus](https://reeffactory.com/product/kh-keeper-plus/) device
- A **Smart Reef account** (the same credentials used in the Smart Reef mobile app)
- Your device's **serial number** (found in the Smart Reef app under Device Settings)

---

## Installation

### Via HACS (recommended)

1. Open **HACS** in your Home Assistant instance
2. Go to **Integrations**
3. Click the three-dot menu (⋮) in the top right and choose **Custom repositories**
4. Add the repository URL: `https://github.com/realiztw/reef-factory-kh`
   - Category: **Integration**
5. Click **Add**
6. Find **Reef Factory KH Keeper** in the HACS integration list and click **Download**
7. Restart Home Assistant

### Manual installation

1. Download the [latest release](https://github.com/realiztw/reef-factory-kh/releases/latest)
2. Copy the `custom_components/reef_factory_kh` folder into your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

---

## Configuration

1. Go to **Settings → Integrations → + Add Integration**
2. Search for **Reef Factory KH Keeper**
3. Enter your credentials:
   - **Smart Reef Email** — the email address for your Smart Reef account
   - **Smart Reef Password** — your Smart Reef account password
   - **Device Serial Number** — found in the Smart Reef app under your KH Keeper's Device Settings (e.g. `RFKH012345678901`)
4. Click **Submit**

The integration will validate your credentials and create all entities automatically.

> **Multiple devices**: You can add the integration multiple times, once per KH Keeper serial number, if you have more than one device.

---

## Entities

All entities are created under a single device named **KH Keeper `<serial>`**.

| Entity | Type | Unit | Notes |
|--------|------|------|-------|
| KH Value | Sensor | dKH | Latest carbonate hardness reading |
| Reagent Remaining | Sensor | mL | Volume of reagent left in reservoir |
| Last Measurement | Sensor | — | Timestamp of the most recent automated test |
| KH Alarm Low | Sensor | dKH | Low alarm threshold set on the device (diagnostic, disabled by default) |
| KH Alarm High | Sensor | dKH | High alarm threshold set on the device (diagnostic, disabled by default) |

---

## Automation ideas

```yaml
# Alert when reagent is running low
automation:
  trigger:
    platform: numeric_state
    entity_id: sensor.kh_keeper_reagent_remaining
    below: 20
  action:
    service: notify.mobile_app
    data:
      message: "KH Keeper reagent is low — only {{ states('sensor.kh_keeper_reagent_remaining') }} mL remaining!"

# Alert if KH drops out of target range
automation:
  trigger:
    platform: numeric_state
    entity_id: sensor.kh_keeper_kh_value
    below: 7.5
  action:
    service: notify.mobile_app
    data:
      message: "KH has dropped to {{ states('sensor.kh_keeper_kh_value') }} dKH!"
```

---

## Troubleshooting

**"Invalid email or password"** — Check your Smart Reef app credentials. The email/password used here must be for the Smart Reef account, not the Reef Factory website.

**"Could not connect"** — The integration uses a WebSocket connection to `api.reeffactory.com`. Check that your Home Assistant instance has outbound internet access.

**Entities show `unavailable`** — Check the Home Assistant logs under **Settings → System → Logs** and search for `reef_factory_kh` for more detail.

---

## Contributing

Pull requests and bug reports are welcome! Please open an [issue](https://github.com/realiztw/reef-factory-kh/issues) for any problems or feature requests.

---

## Disclaimer

This integration is not affiliated with or endorsed by Reef Factory. It uses the same WebSocket API as the official Smart Reef web application.

## License

[MIT](LICENSE)

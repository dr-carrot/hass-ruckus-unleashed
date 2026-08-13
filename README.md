# Ruckus Unleashed for Home Assistant

A small custom integration that lets you control your **Ruckus Unleashed** Wi-Fi networks from Home Assistant.

It complements the built-in Home Assistant Ruckus integration: it adds the one thing that is missing for automation — **switching individual WLANs (SSIDs) on and off**.

## What it does

Each WLAN on your Ruckus Unleashed controller becomes a Home Assistant **switch**:

```text
switch.main_wifi
switch.iot_wifi
switch.guest_wifi
```

Turning a switch on or off enables/disables that WLAN across your whole Unleashed deployment. You can then use it in automations:

```yaml
action:
  - action: switch.turn_off
    target:
      entity_id: switch.guest_wifi
```

Each physical access point is also registered as a Home Assistant **device** (identified by serial number), so you can see your AP fleet in the UI.

## Requirements

- Home Assistant (the integration uses the `aioruckus` library)
- A Ruckus Unleashed controller reachable over HTTP/HTTPS

## Installation

### HACS (recommended)

1. Add this repository to HACS as a custom repository (category: **Integration**).
2. Install **Ruckus Unleashed** from HACS.
3. Restart Home Assistant.

### Manual

Copy the `custom_components/ruckus_unleashed` directory into your Home Assistant `config/custom_components/` directory, then restart Home Assistant.

## Setup

1. Go to **Settings → Devices & services → Add integration**.
2. Search for **Ruckus Unleashed**.
3. Enter:
   - **Controller hostname or IP address**
   - **Username** (controller admin login)
   - **Password**
   - **Verify SSL certificate** — leave enabled unless your controller uses a self-signed certificate.

If your Unleashed controller uses a self-signed certificate, you may need to uncheck *Verify SSL certificate*.

### Options

After setup you can adjust, without re-adding the integration:

- **Verify SSL certificate**
- **Polling interval** (default 60 s, minimum 10 s)

Under **Settings → Devices & services**, select the integration and **Options**.

## Re-authentication

If your controller credentials change, the integration will prompt you to re-enter them (the same *Username* / *Password* form appears automatically).

## Supported features

- One switch per WLAN, reflecting the controller's actual enabled/disabled state
- Enable / disable WLANs
- One Home Assistant device per physical AP (serial number, model, firmware)
- Automatic credential re-auth flow
- Configurable polling interval
- SSL verification toggle for self-signed certificates

## Not included (by design)

- Client / device tracking — the native Ruckus integration already handles this.
- WLAN statistics, AP control/reboot, WLAN password management, or WLAN create/edit/delete.

## Troubleshooting

### Integration fails to connect

- Check that the hostname/IP and credentials are correct.
- If the controller uses a self-signed certificate, uncheck *Verify SSL certificate* during setup.

### Switches show unavailable

- The controller could not be reached on the last poll. Check the connection and that the controller is online.
- A WLAN that no longer exists on the controller also becomes unavailable rather than being deleted immediately.

### Enable/disable state is inverted

`aioruckus` reports a WLAN's state through the `enable-type` field, where `0` means enabled and `1` means disabled. The integration follows that convention. If you believe a switch's on/off state does not match what your controller reports, enable debug logging and open an issue:

```yaml
logger:
  default: warning
  logs:
    custom_components.ruckus_unleashed: debug
```

## Credits

- Uses the [aioruckus](https://github.com/ms264556/aioruckus) library to talk to the Ruckus Unleashed AJAX interface.

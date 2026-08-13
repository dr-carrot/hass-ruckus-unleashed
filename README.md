# Ruckus Unleashed WLANs for Home Assistant

A custom Home Assistant integration that lets you control the **WLANs** of your **Ruckus Unleashed** Wi-Fi networks.

It complements the **built-in** Home Assistant Ruckus integration (`ruckus_unleashed`): it adds what's missing for automation — switching individual WLANs (SSIDs) on and off.

## Features

- Enable / disable individual WLANs as Home Assistant **switches**
- One Home Assistant **device** per physical access point (serial number, model, firmware)
- Configurable polling interval (default 60 s, minimum 10 s)
- SSL verification toggle for self-signed certificates
- Automatic re-authentication when controller credentials change

## Requirements

- Home Assistant
- A Ruckus Unleashed controller reachable over HTTP/HTTPS

## Installation

### HACS (recommended)

1. Add this repository to HACS as a custom repository (category: **Integration**).
2. Install **Ruckus Unleashed** from HACS.
3. Restart Home Assistant.

### Manual

Copy the `custom_components/hacs_ruckus_unleashed` directory into your Home Assistant `config/custom_components/` directory, then restart Home Assistant.

## Configuration

### Adding the integration

1. Go to **Settings → Devices & services → Add integration**.
2. Search for **Ruckus Unleashed WLANs**.
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

### Re-authentication

If your controller credentials change, the integration will prompt you to re-enter them (the same *Username* / *Password* form appears automatically).

## Entities

### WLAN switches

Each WLAN on your controller becomes a switch that reflects the controller's actual enabled/disabled state:

```text
switch.main_wifi
switch.iot_wifi
switch.guest_wifi
```

Turning a switch on or off enables/disables that WLAN across your whole Unleashed deployment. Use it in automations:

```yaml
action:
  - action: switch.turn_off
    target:
      entity_id: switch.guest_wifi
```

Available attributes: `ssid`, `is_guest`, `encryption`.

### Access points

Each physical access point is registered as a Home Assistant device, identified by serial number, with model and firmware metadata:

```text
Ruckus Unleashed
├── AP - Office
├── AP - Living Room
└── AP - Basement
```

## Troubleshooting

### Integration fails to connect

- Check that the hostname/IP and credentials are correct.
- If the controller uses a self-signed certificate, uncheck *Verify SSL certificate* during setup.

### Switches show unavailable

- The controller could not be reached on the last poll. Check the connection and that the controller is online.
- A WLAN that no longer exists on the controller also becomes unavailable rather than being deleted immediately.

### Enable/disable state seems inverted

`aioruckus` reports a WLAN's state through the `enable-type` field, where `0` means enabled and `1` means disabled. The integration follows that convention.

### Debug logging

If something isn't behaving, enable debug logging and open an issue:

```yaml
logger:
  default: warning
  logs:
    custom_components.hacs_ruckus_unleashed: debug
```

## Credits

- Uses the [aioruckus](https://github.com/ms264556/aioruckus) library to talk to the Ruckus Unleashed AJAX interface.

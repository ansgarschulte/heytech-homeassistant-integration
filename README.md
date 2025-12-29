# Heytech Home Assistant Integration

[![GitHub Release][releases-shield]][releases]
[![Version](https://img.shields.io/badge/version-1.5.0-blue.svg)](https://github.com/ansgarschulte/heytech-homeassistant-integration/releases)
[![License][license-shield]](LICENSE)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/)

**🎉 Version 1.5.0** - Complete feature set with scenes, groups, sensors, and advanced automation!

Control your Heytech shutter system directly from Home Assistant.

[releases-shield]: https://img.shields.io/github/release/ansgarschulte/heytech-homeassistant-integration.svg
[releases]: https://github.com/ansgarschulte/heytech-homeassistant-integration/releases
[license-shield]: https://img.shields.io/github/license/ansgarschulte/heytech-homeassistant-integration.svg

---

## Features

✅ **Shutters** - Full control of all configured shutters  
✅ **Groups** - Control multiple shutters as groups (up to 8)  
✅ **Scenes** - Activate predefined scenarios  
✅ **Sensors** - Temperature, humidity, wind, rain, brightness  
✅ **Services** - Logbook access, group control, time sync  
✅ **Tilt Control** - Jalousie/blind angle control  
✅ **Time Sync** - Button entity and service for time synchronization  

---

## Installation

### HACS (Recommended)

1. Add custom repository: `https://github.com/ansgarschulte/heytech-homeassistant-integration`
2. Install "Heytech" from HACS
3. Restart Home Assistant
4. Add integration via UI

### Manual

1. Copy `custom_components/heytech` to your `config/custom_components/`
2. Restart Home Assistant
3. Add integration via UI

---

## Configuration

**Settings** → **Devices & Services** → **Add Integration** → Search "Heytech"

Required:
- **Host**: IP address of controller (e.g. `192.168.1.100`)
- **Port**: `1002` (default)
- **PIN**: Your PIN code (if configured)

---

## What You Get

### 🎛️ Entities

**Covers**
- All shutters as `cover.shutter_name`
- All groups as `cover.group_1` through `cover.group_8`
- Control: open, close, stop, set position, tilt (jalousies)

**Sensors**
- `sensor.indoor_temperature` / `sensor.outdoor_temperature`
- `sensor.relative_humidity`
- `sensor.current_wind_speed` / `sensor.maximum_wind_speed`
- `sensor.brightness` (with Lux conversion)
- `binary_sensor.rain`
- `binary_sensor.alarm`
- `binary_sensor.automation_status`
- `sensor.logbook_entries`
- `sensor.model` - Device model (e.g., "HEYtech RS879M")
- `sensor.firmware_version` - Firmware version (e.g., "8.027r")
- `sensor.device_number` - Device serial number

**Scenes** (if configured on controller)
- `scene.morning`, `scene.evening`, etc.

### 🛠️ Services

**Read Logbook**
```yaml
service: heytech.read_logbook
data:
  max_entries: 100
```

**Clear Logbook**
```yaml
service: heytech.clear_logbook
```

**Control Group**
```yaml
service: heytech.control_group
data:
  group_number: 1
  action: "open"  # or "close", "stop", 0-100
```

**Export Shutters Configuration**
```yaml
service: heytech.export_shutters_config
data:
  filename: "my_backup"
```

**Import Shutters Configuration**
```yaml
service: heytech.import_shutters_config
data:
  config_data: |
    {
      "version": "1.0",
      "shutters": {
        "Living Room": "1,2,3",
        "Bedroom": "4,5"
      }
    }
```

**Synchronize Time**
```yaml
service: heytech.sync_time
```

Sends current Home Assistant date/time to the controller. Useful for:
- Daily automation (e.g., at 3 AM)
- After controller restarts
- Initial setup

**Example Automation:**
```yaml
automation:
  - alias: "Daily Time Sync"
    trigger:
      - platform: time
        at: "03:00:00"
    action:
      - service: heytech.sync_time
```

---

## Backup & Restore

### Via UI (Options)
1. **Settings** → **Devices & Services** → **Heytech**
2. Click **Configure** (3 dots menu)
3. Choose **Export Configuration** to backup
4. Choose **Import Configuration** to restore

### Via Services
- Use `heytech.export_shutters_config` service
- Use `heytech.import_shutters_config` service
- Configuration is JSON format for easy editing

---

## Testing

### Quick API Test
```bash
python tests/test_api.py YOUR_IP --pin YOUR_PIN
```

### Docker Test Environment
```bash
docker-compose up -d
# Access at http://localhost:8123
```

See `DEVELOPMENT.md` for detailed testing guide.

---

## Known Limitations

⚠️ **Scenarios** must be configured on controller first  
ℹ️ **Group names** are generic ("Group 1", "Group 2") as controller sends bitmasks

---

## Troubleshooting

**No shutters found?**
- Check IP/port in integration settings
- Verify PIN if controller is protected
- Check logs: Settings → System → Logs

**No groups visible?**
- Groups must be configured on controller
- Reload integration after configuration

**No scenes?**
- Configure scenarios in HeyTech software
- Reload integration

---

## Documentation

- `DEVELOPMENT.md` - Development & testing guide
- `CHANGELOG.md` - Version history & features
- `CONTRIBUTING.md` - How to contribute

---

## Support

🐛 [Issues](https://github.com/ansgarschulte/heytech-homeassistant-integration/issues)  
💬 [Discussions](https://github.com/ansgarschulte/heytech-homeassistant-integration/discussions)

---

## License

MIT License - see [LICENSE](LICENSE)

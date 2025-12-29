# Development Guide

Complete guide for developing and testing the Heytech integration.

---

## Quick Start

```bash
# 1. Start test environment
docker-compose up -d

# 2. Access Home Assistant
open http://localhost:8123

# 3. Make code changes
vim custom_components/heytech/api.py

# 4. Reload
./dev-reload.sh

# 5. Check logs
docker-compose logs -f homeassistant | grep heytech
```

---

## Setup

### Docker Environment (Recommended)

**Start**
```bash
docker-compose up -d
```

**Access**: http://localhost:8123  
**Live Code**: Changes in `custom_components/` are immediately available  
**Reload**: Use `./dev-reload.sh` after changes

**Stop**
```bash
docker-compose down
```

### Standalone Testing

Test API without Home Assistant:

```bash
# Simple test
python tests/test_api.py 192.168.1.100

# With PIN
python tests/test_api.py 192.168.1.100 --pin 1234

# See all options
python tests/test_api.py --help
```

---

## Development Workflow

### 1. Make Changes

```bash
# Edit any file in custom_components/heytech/
vim custom_components/heytech/api.py
```

### 2. Reload Integration

**Option A: Script (fastest)**
```bash
./dev-reload.sh
# Choose 1 for quick reload
```

**Option B: Manual**
```bash
docker exec homeassistant-heytech-test ha core reload
```

**Option C: Full restart**
```bash
docker-compose restart
```

**Option D: Home Assistant UI**
- Developer Tools → YAML → Quick Reload

### 3. Check Logs

```bash
# Follow logs
docker-compose logs -f homeassistant

# Filter for Heytech
docker-compose logs -f homeassistant | grep heytech

# Show errors
docker-compose logs homeassistant | grep -i error
```

### 4. Debug

Enable debug logging in `config/configuration.yaml`:
```yaml
logger:
  default: info
  logs:
    custom_components.heytech: debug
    custom_components.heytech.api: debug
```

---

## Testing

### Syntax Check

```bash
python3 -m py_compile custom_components/heytech/*.py
```

### Run Standalone Tests

```bash
python tests/test_api.py YOUR_IP
```

**Tests included:**
1. Connection test
2. Shutter discovery
3. Position reading
4. Climate data
5. Scenario discovery
6. Group discovery
7. Automation status
8. Logbook access

### Test in Home Assistant

1. **Check Entities**
   - Developer Tools → States
   - Filter by "heytech"

2. **Test Services**
   - Developer Tools → Services
   - Search "heytech"

3. **Check Integration**
   - Settings → Devices & Services → Heytech

---

## File Structure

```
custom_components/heytech/
├── __init__.py          # Entry point, services
├── api.py               # Protocol implementation
├── config_flow.py       # Configuration UI
├── const.py             # Constants
├── coordinator.py       # Data updates
├── cover.py             # Shutter entities
├── data.py              # Data models
├── entity.py            # Base entity
├── manifest.json        # Metadata
├── parse_helper.py      # Protocol parsers
├── scene.py             # Scene entities
├── sensor.py            # Sensor entities
├── services.yaml        # Service definitions
└── translations/        # UI translations
```

### Common Changes

| Task | Files to Edit |
|------|---------------|
| Add command | `parse_helper.py`, `api.py` |
| Add sensor | `sensor.py` |
| Add service | `services.yaml`, `__init__.py` |
| Fix parser | `parse_helper.py` |
| Change behavior | `cover.py`, `sensor.py`, `scene.py` |

---

## Troubleshooting

### Integration Won't Load

```bash
# Check logs
docker-compose logs homeassistant | grep -i error

# Restart container
docker-compose restart

# Check syntax
python3 -m py_compile custom_components/heytech/*.py
```

### Changes Not Visible

```bash
# Verify files are mounted
docker exec homeassistant-heytech-test ls -la /config/custom_components/heytech/

# Check timestamp
docker exec homeassistant-heytech-test stat /config/custom_components/heytech/api.py

# Force restart
docker-compose restart
```

### Port Not Accessible

If http://localhost:8123 doesn't work:

```bash
# Check container
docker ps | grep homeassistant

# Check port mapping
docker port homeassistant-heytech-test

# Should show: 8123/tcp -> 0.0.0.0:8123
```

---

## Tips

### Fast Iteration

```bash
# Check syntax + reload in one command
python3 -m py_compile custom_components/heytech/*.py && ./dev-reload.sh
```

### Keep Logs Open

```bash
# In separate terminal
docker-compose logs -f homeassistant | grep heytech
```

### Clean Start

```bash
# Stop and remove everything
docker-compose down
rm -rf config/

# Fresh start
docker-compose up -d
```

---

## CI/CD

### Pre-commit Checks

```bash
# Syntax
python3 -m py_compile custom_components/heytech/*.py

# Code style (optional)
pip install black
black custom_components/heytech/

# Type checking (optional)
pip install mypy
mypy custom_components/heytech/
```

---

## Resources

- [Home Assistant Developer Docs](https://developers.home-assistant.io/)
- [Integration Structure](https://developers.home-assistant.io/docs/creating_component_index/)
- [Config Flow](https://developers.home-assistant.io/docs/config_entries_config_flow_handler/)

---

## Getting Help

- Check `CHANGELOG.md` for implemented features
- See `README.md` for usage
- Open issue on GitHub for bugs

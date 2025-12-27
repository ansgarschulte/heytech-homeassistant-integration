# 🔧 Development Guide

## Live Code Reloading

Dein Code ist **live gemountet**! Jede Änderung in `custom_components/heytech/` ist sofort im Container sichtbar.

## Quick Start Development

```bash
# 1. Container starten
docker-compose up -d

# 2. Code ändern
vim custom_components/heytech/api.py

# 3. Quick Reload (empfohlen)
./dev-reload.sh

# Oder manuell:
docker exec homeassistant-heytech-test ha core reload
```

## Development Workflow

### Setup
```bash
# Start Home Assistant test instance
docker-compose up -d

# Wait for startup (first time ~1 minute)
docker-compose logs -f homeassistant

# Access at http://localhost:8123
# Create admin account
# Add Heytech integration
```

### Make Changes
```bash
# Edit any file in custom_components/heytech/
vim custom_components/heytech/api.py

# Syntax check (optional)
python3 -m py_compile custom_components/heytech/api.py
```

### Reload Integration

#### Option 1: Script (Recommended)
```bash
./dev-reload.sh
# Choose option 1 for quick reload
```

#### Option 2: Manual Quick Reload
```bash
docker exec homeassistant-heytech-test ha core reload
```

#### Option 3: Full Restart (if quick reload doesn't work)
```bash
docker-compose restart
```

#### Option 4: In Home Assistant UI
1. Go to **Developer Tools** → **YAML**
2. Click **Quick Reload** or **Restart**

### View Logs

```bash
# Follow logs
docker-compose logs -f homeassistant

# Filter for Heytech
docker-compose logs -f homeassistant | grep -i heytech

# Last 50 lines
docker-compose logs --tail=50 homeassistant

# Only errors
docker-compose logs homeassistant | grep -i error
```

## File Structure & What to Edit

```
custom_components/heytech/
├── __init__.py          # Main entry point, services
├── api.py               # API client, protocol handling
├── config_flow.py       # Configuration UI
├── const.py             # Constants
├── coordinator.py       # Data update coordinator
├── cover.py             # Cover entities (shutters, groups)
├── data.py              # Data models
├── entity.py            # Base entity class
├── manifest.json        # Integration metadata
├── parse_helper.py      # Protocol parsers
├── scene.py             # Scene entities (scenarios)
├── sensor.py            # Sensor entities
└── services.yaml        # Service definitions
```

### Common Changes

| What You Want | File to Edit |
|---------------|-------------|
| Add new command | `parse_helper.py` + `api.py` |
| Add new sensor | `sensor.py` |
| Add new service | `services.yaml` + `__init__.py` |
| Change cover behavior | `cover.py` |
| Fix parsing | `parse_helper.py` |
| Add new feature | `api.py` + entity files |

## Testing Changes

### 1. Syntax Check
```bash
python3 -m py_compile custom_components/heytech/*.py
```

### 2. Check Integration Loads
```bash
# Reload and check logs
./dev-reload.sh
# Choose option 1

# Or manually:
docker exec homeassistant-heytech-test ha core reload
docker-compose logs --tail=50 homeassistant | grep heytech
```

### 3. Test in UI
1. Go to **Developer Tools** → **States**
2. Filter by "heytech"
3. Verify entities appear
4. Test controls

### 4. Test Services
1. Go to **Developer Tools** → **Services**
2. Search for "heytech"
3. Test service calls

### 5. Check Logs for Errors
```bash
docker-compose logs homeassistant | grep -i error | grep -i heytech
```

## Common Issues & Solutions

### Issue: Integration doesn't reload
**Solution:**
```bash
# Full restart
docker-compose restart

# Or rebuild
docker-compose down
docker-compose up -d
```

### Issue: Syntax error
**Solution:**
```bash
# Check syntax
python3 -m py_compile custom_components/heytech/api.py

# View error in logs
docker-compose logs --tail=100 homeassistant | grep -i error
```

### Issue: Entity not appearing
**Solution:**
```bash
# Check if integration loaded
docker-compose logs homeassistant | grep "Heytech"

# Force reload config entry
# In HA UI: Settings → Devices & Services → Heytech → Reload
```

### Issue: Changes not visible
**Solution:**
```bash
# Verify files are mounted
docker exec homeassistant-heytech-test ls -la /config/custom_components/heytech/

# Check file timestamp
docker exec homeassistant-heytech-test stat /config/custom_components/heytech/api.py

# Force full restart
docker-compose restart
```

## Debug Mode

### Enable Debug Logging

Add to `config/configuration.yaml`:
```yaml
logger:
  default: info
  logs:
    custom_components.heytech: debug
    custom_components.heytech.api: debug
```

Then reload:
```bash
docker exec homeassistant-heytech-test ha core reload
```

### View Debug Logs
```bash
docker-compose logs -f homeassistant | grep -i "custom_components.heytech"
```

## Performance Testing

### Check API Response Times
Add to `api.py`:
```python
import time

async def some_method(self):
    start = time.time()
    # ... your code ...
    _LOGGER.debug(f"Operation took {time.time() - start:.2f}s")
```

### Monitor Container Resources
```bash
docker stats homeassistant-heytech-test
```

## Clean Start

```bash
# Stop everything
docker-compose down

# Remove config (⚠️ loses all settings)
rm -rf config

# Fresh start
docker-compose up -d
```

## Backup & Restore

### Backup Config
```bash
tar czf hass-config-backup.tar.gz config/
```

### Restore Config
```bash
tar xzf hass-config-backup.tar.gz
docker-compose restart
```

## Quick Commands Reference

```bash
# Start
docker-compose up -d

# Stop
docker-compose down

# Restart
docker-compose restart

# Logs
docker-compose logs -f

# Quick reload
./dev-reload.sh

# Enter container
docker exec -it homeassistant-heytech-test bash

# Check integration
docker exec homeassistant-heytech-test ha core check

# View entities
docker exec homeassistant-heytech-test ha entity list | grep heytech
```

## CI/CD Integration

### Pre-commit Checks
```bash
# Syntax check
python3 -m py_compile custom_components/heytech/*.py

# Code style (optional)
pip install black
black custom_components/heytech/

# Type checking (optional)
pip install mypy
mypy custom_components/heytech/
```

## VS Code Integration

### Recommended Extensions
- Python
- Docker
- YAML

### settings.json
```json
{
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": true,
  "python.formatting.provider": "black"
}
```

## Tips & Tricks

1. **Keep logs open** while developing:
   ```bash
   docker-compose logs -f homeassistant | grep heytech
   ```

2. **Use the reload script** for fastest iteration:
   ```bash
   ./dev-reload.sh
   ```

3. **Check syntax before reload** to avoid crashes:
   ```bash
   python3 -m py_compile custom_components/heytech/*.py && ./dev-reload.sh
   ```

4. **Test standalone** before Docker:
   ```bash
   python3 -c "import sys; sys.path.insert(0, '.'); from custom_components.heytech.api import HeytechApiClient; print('OK')"
   ```

5. **Git commits** after each working feature:
   ```bash
   git add -A
   git commit -m "feat: add XYZ"
   ```

## Need Help?

Check these files:
- `README.md` - Features overview
- `TESTING.md` - Quick tests
- `CHANGELOG.md` - Implementation details
- `IMPLEMENTATION_SUMMARY.md` - Complete overview

Happy coding! 🚀

# Test Environment Setup

## Option 1: Docker (Recommended - Full Home Assistant)

```bash
# Start Home Assistant with Heytech integration
docker-compose up -d

# Access at http://localhost:8123
# Add Heytech integration via UI

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

## Option 2: Standalone Python Test

```bash
# Install only what's needed for testing API
pip install aiohttp

# Run simple test (no HA dependencies)
python3 -c "
import asyncio
import sys
sys.path.insert(0, '.')

# Mock HA modules
class M:
    def __getattr__(self, n): return M()
    def __call__(self, *a, **k): return M()
for mod in ['homeassistant', 'homeassistant.core', 'homeassistant.helpers', 
            'homeassistant.helpers.update_coordinator', 'homeassistant.config_entries',
            'homeassistant.const', 'homeassistant.exceptions', 'homeassistant.helpers.entity_platform',
            'homeassistant.helpers.device_registry', 'homeassistant.helpers.entity_registry',
            'homeassistant.helpers.config_validation', 'homeassistant.components.cover',
            'homeassistant.components.sensor', 'homeassistant.components.binary_sensor',
            'homeassistant.components.scene', 'voluptuous']:
    sys.modules[mod] = M()

from custom_components.heytech.api import HeytechApiClient

async def test(host):
    client = HeytechApiClient(host=host, pin='')
    await client.async_test_connection()
    shutters = await client.async_read_heytech_data()
    print(f'✅ Found {len(shutters)} shutters')
    print(f'✅ Scenarios: {len(client.get_scenarios())}')
    print(f'✅ Groups: {len(client.get_groups())}')
    await client.stop()

asyncio.run(test('YOUR_IP_HERE'))
"
```

## Quick Test Commands

Replace `192.168.1.100` with your Heytech controller IP:

### Test Connection
```python
python3 -c "
import asyncio
from custom_components.heytech.api import HeytechApiClient
asyncio.run(HeytechApiClient('192.168.1.100').async_test_connection())
print('✅ Connection OK')
"
```

### List All Features
```python
python3 <<EOF
import asyncio, sys
sys.path.insert(0, '.')
[sys.modules.__setitem__(m, type('M', (), {'__getattr__': lambda *a: sys.modules[m]})) 
 for m in ['homeassistant', 'homeassistant.core', 'homeassistant.helpers', 
           'homeassistant.helpers.update_coordinator', 'voluptuous']]

from custom_components.heytech.api import HeytechApiClient

async def test():
    c = HeytechApiClient('192.168.1.100', pin='')
    await c.async_read_heytech_data()
    print(f'Shutters: {len(c.shutters)}')
    print(f'Scenarios: {c.get_scenarios()}')
    print(f'Groups: {c.get_groups()}')
    print(f'Climate: {c.get_climate_data()}')
    await c.stop()

asyncio.run(test())
EOF
```

## Features to Test

1. **Shutters** - Check if all are discovered
2. **Scenarios** - Should see all configured scenes
3. **Groups** - Should see all groups as cover entities
4. **Sensors** - Temperature, wind, rain, alarm, etc.
5. **Services** - read_logbook, clear_logbook, control_group
6. **Tilt Control** - For jalousies (if configured)

## Troubleshooting

If compilation fails, it's usually due to missing HA modules - this is normal for standalone testing.
The Docker setup includes everything needed.

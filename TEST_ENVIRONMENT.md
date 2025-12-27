# Heytech Home Assistant Test Environment

This directory contains a complete test environment for the Heytech integration.

## Quick Start with Docker

### 1. Start Home Assistant Test Instance

```bash
docker-compose up -d
```

This will:
- Start a Home Assistant instance on `http://localhost:8123`
- Automatically mount the `custom_components/heytech` integration
- Create a `config` directory for Home Assistant configuration

### 2. Initial Setup

1. Open `http://localhost:8123` in your browser
2. Create an admin account
3. Go to **Settings** → **Devices & Services** → **Add Integration**
4. Search for "Heytech" and add it
5. Enter your Heytech controller details:
   - Host/IP: Your controller IP address
   - Port: 1002 (default)
   - PIN: Your PIN (if required)

### 3. Stop the Test Environment

```bash
docker-compose down
```

To completely remove everything including the config:
```bash
docker-compose down -v
rm -rf config
```

## Test API Without Home Assistant

### Requirements

Install Python dependencies:
```bash
pip install -r requirements.txt
```

### Run Test Script

```bash
# Basic test (read-only)
python tests/test_api.py YOUR_IP_ADDRESS

# With PIN
python tests/test_api.py YOUR_IP_ADDRESS --pin 1234

# Interactive mode
python tests/test_api.py YOUR_IP_ADDRESS --interactive

# Custom port
python tests/test_api.py YOUR_IP_ADDRESS --port 1002
```

### Interactive Mode Menu

```
1. Read positions - Get current shutter positions
2. Read climate data - Temperature, humidity, brightness, etc.
3. List scenarios - Show all available scenarios
4. List groups - Show all configured groups
5. Read logbook - Last 10 entries
6. Show automation params - Shading, wind, rain parameters
7. Control shutter - Set position of a specific channel
8. Activate scenario - Trigger a predefined scenario
9. Control group - Control a group of shutters
0. Run all tests - Execute complete test suite
q. Quit
```

## Manual Testing with Python

```python
import asyncio
from custom_components.heytech.api import HeytechApiClient

async def test():
    client = HeytechApiClient(host="192.168.1.100", pin="")
    
    # Discover shutters
    shutters = await client.async_read_heytech_data()
    print("Shutters:", shutters)
    
    # Get positions
    positions = await client.async_read_shutters_positions()
    print("Positions:", positions)
    
    # Get climate data
    climate = client.get_climate_data()
    print("Climate:", climate)
    
    # Get scenarios
    scenarios = client.get_scenarios()
    print("Scenarios:", scenarios)
    
    # Get groups
    groups = client.get_groups()
    print("Groups:", groups)
    
    # Control a shutter (be careful!)
    # await client.add_command("50", [1])  # Set channel 1 to 50%
    
    # Activate a scenario (be careful!)
    # await client.async_activate_scenario(1)
    
    await client.stop()

asyncio.run(test())
```

## Troubleshooting

### Home Assistant doesn't see the integration

1. Check if the integration is properly mounted:
   ```bash
   docker exec homeassistant-heytech-test ls -la /config/custom_components/heytech
   ```

2. Restart Home Assistant:
   ```bash
   docker-compose restart
   ```

3. Check logs:
   ```bash
   docker-compose logs -f homeassistant
   ```

### Can't connect to Heytech controller

1. Verify the controller is reachable:
   ```bash
   ping YOUR_CONTROLLER_IP
   telnet YOUR_CONTROLLER_IP 1002
   ```

2. Check if port 1002 is open
3. Verify PIN if your controller requires one

### Integration errors

Check Home Assistant logs:
```bash
docker-compose logs -f homeassistant | grep heytech
```

Or in the Home Assistant UI:
**Settings** → **System** → **Logs**

## Development Workflow

1. Make changes to code in `custom_components/heytech/`
2. Restart Home Assistant:
   ```bash
   docker-compose restart
   ```
3. Test changes in Home Assistant UI
4. Check logs for errors

## Testing Individual Features

### Test Scenarios
```python
python tests/test_api.py YOUR_IP --interactive
# Choose option 3 to list scenarios
# Choose option 8 to activate one (careful!)
```

### Test Groups
```python
python tests/test_api.py YOUR_IP --interactive
# Choose option 4 to list groups
# Choose option 9 to control a group (careful!)
```

### Test Logbook
```python
python tests/test_api.py YOUR_IP --interactive
# Choose option 5 to read last 10 logbook entries
```

### Test Sensors
1. Open Home Assistant
2. Go to **Developer Tools** → **States**
3. Filter by "heytech"
4. You should see all sensors (temperature, wind, rain, etc.)

### Test Services
1. Go to **Developer Tools** → **Services**
2. Search for "heytech"
3. You should see:
   - `heytech.read_logbook`
   - `heytech.clear_logbook`
   - `heytech.control_group`

## File Structure

```
heytech-homeassistant-integration/
├── custom_components/heytech/    # Integration code
│   ├── __init__.py               # Entry point
│   ├── api.py                    # API client
│   ├── cover.py                  # Shutter entities
│   ├── sensor.py                 # Sensor entities
│   ├── scene.py                  # Scenario entities
│   ├── services.yaml             # Service definitions
│   └── ...
├── tests/
│   └── test_api.py               # Test script
├── config/                       # Home Assistant config (created by Docker)
├── docker-compose.yml            # Docker setup
└── TEST_ENVIRONMENT.md           # This file
```

## Safety Notes

⚠️ **BE CAREFUL when testing control commands!**

The test script skips dangerous operations by default:
- Shutter control (moving shutters)
- Scenario activation
- Group control

To enable these tests, you must manually uncomment the code in `tests/test_api.py`.

Always test with non-critical shutters first!

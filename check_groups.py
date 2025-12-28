#!/usr/bin/env python3
"""Check what groups are discovered."""
import asyncio
import sys
sys.path.insert(0, '.')

# Mock HA modules
class M:
    def __getattr__(self, n): return M()
    def __call__(self, *a, **k): return M()

for mod in ['homeassistant', 'homeassistant.core', 'homeassistant.helpers',
            'homeassistant.helpers.update_coordinator', 'homeassistant.config_entries',
            'homeassistant.const', 'homeassistant.exceptions',
            'homeassistant.helpers.entity_platform', 'homeassistant.helpers.device_registry',
            'homeassistant.helpers.entity_registry', 'homeassistant.helpers.config_validation',
            'homeassistant.components.cover', 'homeassistant.components.sensor',
            'homeassistant.components.binary_sensor', 'homeassistant.components.scene',
            'voluptuous']:
    sys.modules[mod] = M()

from custom_components.heytech.api import HeytechApiClient

async def check():
    client = HeytechApiClient('10.0.1.6', pin='')
    await client.async_read_heytech_data()
    
    print("="*60)
    print("GRUPPEN ANALYSE")
    print("="*60)
    print(f"\nAnzahl Gruppen: {len(client.groups)}")
    print(f"\nGruppen-Dict:")
    for num, info in client.groups.items():
        print(f"  Gruppe {num}: {info}")
    
    print(f"\nScenarien: {len(client.scenarios)}")
    for num, name in list(client.scenarios.items())[:5]:
        print(f"  {num}. {name}")
    
    await client.stop()

asyncio.run(check())

#!/usr/bin/env python3
"""
Test script for Heytech API client.

This script allows you to test all features of the Heytech integration locally
without Home Assistant.

Usage:
    python tests/test_api.py <IP_ADDRESS> [--port 1002] [--pin YOUR_PIN]

Examples:
    python tests/test_api.py 192.168.1.100
    python tests/test_api.py 192.168.1.100 --pin 1234
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock Home Assistant modules
class MockModule:
    def __getattr__(self, name):
        return MockModule()
    def __call__(self, *args, **kwargs):
        return MockModule()
    def __getitem__(self, key):
        return MockModule()

# Mock all HA dependencies
for mod in [
    'homeassistant', 'homeassistant.core', 'homeassistant.helpers',
    'homeassistant.helpers.update_coordinator', 'homeassistant.config_entries',
    'homeassistant.const', 'homeassistant.exceptions',
    'homeassistant.helpers.entity_platform', 'homeassistant.helpers.device_registry',
    'homeassistant.helpers.entity_registry', 'homeassistant.helpers.config_validation',
    'homeassistant.components.cover', 'homeassistant.components.sensor',
    'homeassistant.components.binary_sensor', 'homeassistant.components.scene',
    'homeassistant.data_entry_flow', 'homeassistant.helpers.selector',
    'voluptuous'
]:
    sys.modules[mod] = MockModule()

from custom_components.heytech.api import HeytechApiClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
_LOGGER = logging.getLogger(__name__)


async def test_connection(client: HeytechApiClient) -> bool:
    """Test basic connection."""
    print("\n" + "="*60)
    print("TEST 1: Connection Test")
    print("="*60)
    try:
        await client.async_test_connection()
        print("✅ Connection successful!")
        return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False


async def test_discovery(client: HeytechApiClient) -> None:
    """Test shutter discovery."""
    print("\n" + "="*60)
    print("TEST 2: Shutter Discovery")
    print("="*60)
    
    shutters = await client.async_read_heytech_data()
    print(f"✅ Found {len(shutters)} shutters:")
    for name, details in list(shutters.items())[:10]:
        print(f"   - {name} (Channel {details['channel']})")
    if len(shutters) > 10:
        print(f"   ... and {len(shutters) - 10} more")


async def test_positions(client: HeytechApiClient) -> None:
    """Test reading positions."""
    print("\n" + "="*60)
    print("TEST 3: Shutter Positions")
    print("="*60)
    
    positions = await client.async_read_shutters_positions()
    print(f"✅ Got {len(positions)} positions:")
    for ch, pos in list(positions.items())[:10]:
        print(f"   Channel {ch}: {pos}%")
    if len(positions) > 10:
        print(f"   ... and {len(positions) - 10} more")


async def test_climate(client: HeytechApiClient) -> None:
    """Test climate data."""
    print("\n" + "="*60)
    print("TEST 4: Climate Data")
    print("="*60)
    
    climate = client.get_climate_data()
    if climate:
        print("✅ Climate data:")
        print(f"   Indoor temp: {climate.get('indoor temperature', 'N/A')}°C")
        print(f"   Outdoor temp: {climate.get('outdoor temperature', 'N/A')}°C")
        print(f"   Brightness: {climate.get('brightness', 'N/A')}")
        print(f"   Wind speed: {climate.get('current wind speed', 'N/A')} km/h")
        print(f"   Rain: {'Yes' if climate.get('rain') == 1 else 'No'}")
        print(f"   Humidity: {climate.get('relative humidity', 'N/A')}%")
    else:
        print("❌ No climate data")


async def test_scenarios(client: HeytechApiClient) -> None:
    """Test scenario discovery."""
    print("\n" + "="*60)
    print("TEST 5: Scenarios")
    print("="*60)
    
    scenarios = client.get_scenarios()
    if scenarios:
        print(f"✅ Found {len(scenarios)} scenarios:")
        for num, name in scenarios.items():
            print(f"   {num}. {name}")
    else:
        print("⚠️  No scenarios configured on controller")
        print("   Configure scenarios in HeyTech software to see them here")


async def test_groups(client: HeytechApiClient) -> None:
    """Test group discovery."""
    print("\n" + "="*60)
    print("TEST 6: Groups")
    print("="*60)
    
    groups = client.get_groups()
    if groups:
        print(f"✅ Found {len(groups)} groups:")
        for num, info in groups.items():
            name = info.get("name", f"Group {num}")
            channels = info.get("channels", [])
            print(f"   {num}. {name}: {len(channels)} channels {channels[:5]}{'...' if len(channels) > 5 else ''}")
    else:
        print("⚠️  No groups found")


async def test_automation_status(client: HeytechApiClient) -> None:
    """Test automation status."""
    print("\n" + "="*60)
    print("TEST 7: Automation Status")
    print("="*60)
    
    status = client.get_automation_status()
    print(f"✅ External automation: {'Enabled' if status else 'Disabled'}")


async def test_logbook(client: HeytechApiClient) -> None:
    """Test logbook."""
    print("\n" + "="*60)
    print("TEST 8: Logbook")
    print("="*60)
    
    count = client.get_logbook_count()
    print(f"✅ Logbook entries: {count}")
    
    if count > 0:
        print("   Reading last 5 entries...")
        entries = await client.async_read_logbook(max_entries=5)
        for entry in entries:
            print(f"   {entry.get('date')} {entry.get('time')} - {entry.get('motor_room')}: {entry.get('direction')}")


async def run_all_tests(host: str, port: int = 1002, pin: str = "") -> None:
    """Run all tests."""
    print("\n" + "="*60)
    print("HEYTECH API TEST SUITE")
    print("="*60)
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"PIN: {'***' if pin else '(none)'}")
    print("="*60)
    
    client = HeytechApiClient(host=host, port=port, pin=pin)
    
    try:
        # Test connection first
        if not await test_connection(client):
            print("\n❌ Cannot proceed without connection")
            return
        
        # Run all discovery tests
        await test_discovery(client)
        await asyncio.sleep(1)
        
        await test_positions(client)
        await asyncio.sleep(1)
        
        await test_climate(client)
        await asyncio.sleep(1)
        
        await test_scenarios(client)
        await asyncio.sleep(1)
        
        await test_groups(client)
        await asyncio.sleep(1)
        
        await test_automation_status(client)
        await asyncio.sleep(1)
        
        await test_logbook(client)
        
        print("\n" + "="*60)
        print("✅ ALL TESTS COMPLETED SUCCESSFULLY!")
        print("="*60)
        print("\nFeature Summary:")
        print(f"  Shutters: {len(client.shutters)}")
        print(f"  Groups: {len(client.groups)}")
        print(f"  Scenarios: {len(client.scenarios)}")
        print(f"  Logbook entries: {client.logbook_count}")
        print(f"  Automation: {'On' if client.automation_status else 'Off'}")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.stop()


def main() -> None:
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Test Heytech API client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tests/test_api.py 192.168.1.100
  python tests/test_api.py 192.168.1.100 --pin 1234
  python tests/test_api.py 10.0.1.6 --port 1002
        """
    )
    parser.add_argument("host", help="Heytech controller IP address")
    parser.add_argument("--port", type=int, default=1002, help="Port (default: 1002)")
    parser.add_argument("--pin", default="", help="PIN code (if required)")
    
    args = parser.parse_args()
    
    try:
        asyncio.run(run_all_tests(args.host, args.port, args.pin))
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)


if __name__ == "__main__":
    main()

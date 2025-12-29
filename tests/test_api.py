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

# Import the API module directly to avoid __init__.py imports
import importlib.util

spec = importlib.util.spec_from_file_location(
    "heytech_api",
    Path(__file__).parent.parent / "custom_components" / "heytech" / "api.py",
)
heytech_api = importlib.util.module_from_spec(spec)


# Mock only what's needed
class MockLogger:
    def debug(self, *args, **kwargs) -> None:
        pass

    def info(self, *args, **kwargs) -> None:
        pass

    def warning(self, *args, **kwargs) -> None:
        pass

    def error(self, *args, **kwargs) -> None:
        pass


sys.modules["custom_components"] = type(sys)("custom_components")
sys.modules["custom_components.heytech"] = type(sys)("heytech")
sys.modules["custom_components.heytech.const"] = type(sys)("const")
sys.modules["custom_components.heytech.const"].LOGGER = MockLogger()

# Load parse_helper first
parse_spec = importlib.util.spec_from_file_location(
    "parse_helper",
    Path(__file__).parent.parent / "custom_components" / "heytech" / "parse_helper.py",
)
parse_helper = importlib.util.module_from_spec(parse_spec)
parse_spec.loader.exec_module(parse_helper)
sys.modules["custom_components.heytech.parse_helper"] = parse_helper

# Now load API
spec.loader.exec_module(heytech_api)
HeytechApiClient = heytech_api.HeytechApiClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
_LOGGER = logging.getLogger(__name__)


async def test_connection(client: HeytechApiClient) -> bool:
    """Test basic connection."""
    try:
        await client.async_test_connection()
    except Exception:
        return False
    else:
        return True


async def test_discovery(client: HeytechApiClient) -> None:
    """Test shutter discovery."""
    shutters = await client.async_read_heytech_data()
    for _name, _details in list(shutters.items())[:10]:
        pass
    if len(shutters) > 10:
        pass


async def test_positions(client: HeytechApiClient) -> None:
    """Test reading positions."""
    positions = await client.async_read_shutters_positions()
    for _ch, _pos in list(positions.items())[:10]:
        pass
    if len(positions) > 10:
        pass


async def test_climate(client: HeytechApiClient) -> None:
    """Test climate data."""
    climate = client.get_climate_data()
    if climate:
        pass
    else:
        pass


async def test_scenarios(client: HeytechApiClient) -> None:
    """Test scenario discovery."""
    scenarios = client.get_scenarios()
    if scenarios:
        for _num, _name in scenarios.items():
            pass
    else:
        pass


async def test_groups(client: HeytechApiClient) -> None:
    """Test group discovery."""
    groups = client.get_groups()
    if groups:
        for num, info in groups.items():
            info.get("name", f"Group {num}")
            info.get("channels", [])
    else:
        pass


async def test_automation_status(client: HeytechApiClient) -> None:
    """Test automation status."""
    client.get_automation_status()


async def test_logbook(client: HeytechApiClient) -> None:
    """Test logbook."""
    count = client.get_logbook_count()

    if count > 0:
        entries = await client.async_read_logbook(max_entries=5)
        for _entry in entries:
            pass


async def run_all_tests(host: str, port: int = 1002, pin: str = "") -> None:
    """Run all tests."""
    client = HeytechApiClient(host=host, port=port, pin=pin)

    try:
        # Test connection first
        if not await test_connection(client):
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

    except Exception:
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
        """,
    )
    parser.add_argument("host", help="Heytech controller IP address")
    parser.add_argument("--port", type=int, default=1002, help="Port (default: 1002)")
    parser.add_argument("--pin", default="", help="PIN code (if required)")

    args = parser.parse_args()

    try:
        asyncio.run(run_all_tests(args.host, args.port, args.pin))
    except KeyboardInterrupt:
        sys.exit(1)


if __name__ == "__main__":
    main()

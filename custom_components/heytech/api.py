"""Sample API Client."""

from __future__ import annotations

import asyncio
import logging

_LOGGER = logging.getLogger(__name__)


class IntegrationHeytechApiClientError(Exception):
    """Exception to indicate a general API error."""


class IntegrationHeytechApiClientCommunicationError(
    IntegrationHeytechApiClientError,
):
    """Exception to indicate a communication error."""


class HeytechApiClient:
    """Heytech API Client."""

    def __init__(self, host: str, port: int, pin: str = '') -> None:
        self._host = host
        self._port = port
        self._pin = pin
        self._queue = []
        self._lock = asyncio.Lock()
        self._processing = False

    def _generate_shutter_command(self, action: str, channels: list):
        command_map = {"open": "up", "close": "down", "stop": "off", "sss": "sss"}
        if action not in command_map:
            _LOGGER.error(f"Unknown action: {action}")
            return

        shutter_command = command_map[action]
        commands = []

        # Prepare the series of commands based on whether a pin is provided
        if self._pin and self._pin != '':
            # If a pin is provided, send the pin commands
            commands.extend([
                "rsc\r\n",
                f"{self._pin}\r\n",
            ])

        for channel in channels:
            commands.extend([
                "rhi\r\n\r\n",
                "rhb\r\n",
                f"{channel}\r\n",
                f"{shutter_command}\r\n\r\n",
                "rhe\r\n\r\n"
            ])

        return commands

    async def add_shutter_command(self, action: str, channels: list):
        """Add commands to the queue and process them."""
        async with self._lock:
            self._queue.extend(self._generate_shutter_command(action, channels))
            if not self._processing:
                self._processing = True
                await self._process_queue()
                self._processing = False

    async def _process_queue(self):
        """Process all commands in the queue."""
        try:
            reader, writer = await asyncio.open_connection(self._host, self._port)

            while self._queue:
                command = self._queue.pop(0)
                writer.write(command.encode('ascii'))
                await writer.drain()
                await asyncio.sleep(0.05)  # Adjust delay as necessary

            writer.close()
            await writer.wait_closed()

        except Exception as e:
            _LOGGER.error(f"Error sending commands: {e}")
            raise IntegrationHeytechApiClientCommunicationError(
                "Error sending commands",
            ) from e
        finally:
            self._queue.clear()

    async def async_test_connection(self):
        """Test connection to the API."""
        await self.add_shutter_command("sss", [])

    async def async_get_data(self):
        pass

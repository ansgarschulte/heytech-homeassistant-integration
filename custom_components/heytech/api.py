"""
Heytech API Client.

This module provides an API client for interacting with Heytech devices.
"""

from __future__ import annotations

import asyncio
import logging
import re

_LOGGER = logging.getLogger(__name__)

COMMAND_DELAY = 0.05  # Delay between commands in seconds


class IntegrationHeytechApiClientError(Exception):
    """Exception to indicate a general API error."""


class IntegrationHeytechApiClientCommunicationError(IntegrationHeytechApiClientError):
    """Exception to indicate a communication error."""

    def __str__(self) -> str:
        """Return a string representation of the error."""
        if self.__cause__:
            return f"Error sending commands: {self.__cause__}"
        return "Error sending commands"


class HeytechApiClient:
    """Heytech API Client."""

    def __init__(self, host: str, port: int, pin: str = "") -> None:
        """Initialize the Heytech API client."""
        self._host = host
        self._port = port
        self._pin = pin
        self._queue: list[str] = []
        self._lock = asyncio.Lock()
        self._processing = False
        self.shutters = {}  # Stores the parsed shutters

    def _generate_shutter_command(self, action: str, channels: list[int]) -> list[str]:
        """Generate shutter commands based on action and channels."""
        command_map = {"open": "up", "close": "down", "stop": "off", "sss": "sss", "smn": "smn"}
        if action not in command_map:
            _LOGGER.error("Unknown action: %s", action)
            message = f"Unknown action: {action}"
            raise ValueError(message)

        shutter_command = command_map[action]
        commands: list[str] = []

        if self._pin:
            # If a pin is provided, send the pin commands
            commands.extend(
                [
                    "rsc\r\n",
                    f"{self._pin}\r\n",
                ]
            )

        if action == "smn":
            commands.append(f"{shutter_command}\r\n")
        else:
            for channel in channels:
                commands.extend(
                    [
                        "rhi\r\n\r\n",
                        "rhb\r\n",
                        f"{channel}\r\n",
                        f"{shutter_command}\r\n\r\n",
                        "rhe\r\n\r\n",
                    ]
                )

        return commands

    async def add_shutter_command(self, action: str, channels: list[int]) -> None:
        """Add commands to the queue and process them."""
        async with self._lock:
            commands = self._generate_shutter_command(action, channels)
            self._queue.extend(commands)
            if not self._processing:
                self._processing = True
                await self._process_queue()
                self._processing = False

    async def _process_queue(self) -> None:
        """Process all commands in the queue."""
        try:
            reader, writer = await asyncio.open_connection(self._host, self._port)

            while self._queue:
                command = self._queue.pop(0)
                writer.write(command.encode("ascii"))
                await writer.drain()
                await asyncio.sleep(COMMAND_DELAY)

                if command.strip() == "smn":
                    await self._listen_for_smn_output(reader)

            writer.close()
            await writer.wait_closed()

        except Exception as exception:
            _LOGGER.exception("Error sending commands")
            raise IntegrationHeytechApiClientCommunicationError from exception
        finally:
            self._queue.clear()

    async def _listen_for_smn_output(self, reader: asyncio.StreamReader) -> None:
        """Listen and parse the output of the 'smn' command."""
        shutters = {}
        try:
            while True:
                line = await reader.readline()
                line = line.decode("ascii").strip()

                if line.startswith("start_smn"):
                    match = re.match(r"start_smn(\d+),(.+?),(\d+),ende_smn", line)
                    if match:
                        channel = int(match.group(1))
                        name = match.group(2).strip()
                        shutters[name] = {"channel": channel}

                elif line.startswith("start_sti"):
                    _LOGGER.info("Finished parsing shutters: %s", shutters)
                    self.shutters = shutters
                    break
        except Exception as e:
            _LOGGER.error("Error while parsing smn output: %s", e)

    async def async_test_connection(self) -> None:
        """Test connection to the API."""
        await self.add_shutter_command("sss", [])

    async def async_get_data(self) -> None:
        """Send 'smn' command to fetch shutters data."""
        await self.add_shutter_command("smn", [])
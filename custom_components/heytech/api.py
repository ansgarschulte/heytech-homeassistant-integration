"""
Heytech API Client.

This module provides an API client for interacting with Heytech devices.
"""

import asyncio
import logging
from asyncio import Queue
from typing import Any

import telnetlib3

from custom_components.heytech.parse_helper import (
    END_SMC,
    END_SMN,
    END_SOP,
    START_SMC,
    START_SMN,
    START_SOP,
    parse_shutter_positions,
    parse_smc_output,
    parse_smn_output,
)

_LOGGER = logging.getLogger(__name__)

COMMAND_DELAY = 0.05


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
    def __init__(self, host: str, port: int = 1002, pin: str = "", idle_timeout=10):
        self._pin = pin
        self.host = host
        self.port = port
        self.idle_timeout = idle_timeout
        self.command_queue = Queue()
        self.connected = False
        self.reader = None
        self.writer = None
        self.last_activity = None
        self.connection_task = None
        self.read_task = None
        self.idle_task = None
        self.max_channels = None
        self.shutter_positions: dict[int, int] = {}
        self.shutters: dict[Any, dict[str, int]] = {}

    async def connect(self):
        if not self.connected:
            try:
                self.reader, self.writer = await telnetlib3.open_connection(
                    self.host, self.port
                )
                self.connected = True
                self.last_activity = asyncio.get_event_loop().time()
                self.read_task = asyncio.create_task(self._read_output())
                self.idle_task = asyncio.create_task(self._idle_checker())
            except Exception as e:
                _LOGGER.error(f"Connection error: {e}")

    async def disconnect(self):
        if self.connected:
            if self.read_task:
                self.read_task.cancel()
            if self.idle_task:
                self.idle_task.cancel()
            self.writer.close()
            self.connected = False

    def _generate_shutter_command(self, action: str, channels: list[int]) -> list[str]:
        """Generate shutter commands based on action and channels."""
        command_map = {
            "open": "up",
            "close": "down",
            "stop": "off",
        }

        if action in command_map:
            shutter_command = command_map[action]
        else:
            shutter_command = action

        commands: list[str] = []

        if self._pin:
            # If a pin is provided, send the pin commands
            commands.extend(
                [
                    "rsc\r\n",
                    f"{self._pin}\r\n",
                ]
            )

        if not channels:
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
        commands = self._generate_shutter_command(action, channels)
        _LOGGER.debug("Adding command to queue: %s", commands)
        for command in commands:
            await self.command_queue.put(command)
        await self.connect()
        if self.connection_task is None or self.connection_task.done():
            self.connection_task = asyncio.create_task(self._process_commands())

    async def async_test_connection(self) -> None:
        """Test connection to the API."""
        await self.add_shutter_command("sti", [])

    async def async_get_data(self) -> dict[Any, dict[str, int]]:
        """Send 'smn' command to fetch shutters data."""
        try:
            await self.add_shutter_command("smc", [])
            await self.add_shutter_command("smn", [])

            max_wait = 50
            while not self.max_channels and max_wait > 0:
                await asyncio.sleep(0.1)

            max_wait = 50
            while len(self.shutters) < self.max_channels and max_wait > 0:
                await asyncio.sleep(0.1)
            return self.shutters
        except IntegrationHeytechApiClientCommunicationError as exc:
            _LOGGER.error("Failed to get data from Heytech API: %s", exc)

    async def async_get_shutter_positions(self) -> dict[int, int]:
        """Send 'sop' command and parse the shutter positions."""
        self.shutter_positions = {}
        await self.add_shutter_command("sop", [])
        # wait for the sop command to be processed
        max_wait = 50
        while not self.shutter_positions and max_wait > 0:
            await asyncio.sleep(0.1)
            max_wait -= 1

        _LOGGER.debug("Returning shutter positions: %s", self.shutter_positions)
        return self.shutter_positions

    async def _process_commands(self):
        while not self.command_queue.empty():
            command = await self.command_queue.get()
            self.writer.write(command)
            await self.writer.drain()
            self.last_activity = asyncio.get_event_loop().time()
            await asyncio.sleep(COMMAND_DELAY)
        self.connection_task = None

    async def _read_output(self):
        while self.connected:
            try:
                line = await self.reader.readline()
                if line == "":
                    break
                if START_SOP in line and END_SOP in line:
                    self.shutter_positions = parse_shutter_positions(line)
                elif START_SMN in line and END_SMN in line:
                    one_shutter = parse_smn_output(line)
                    self.shutters = self.shutters | one_shutter
                elif START_SMC in line and END_SMC in line:
                    self.max_channels = parse_smc_output(line)
            except asyncio.CancelledError:
                break
            except Exception as e:
                _LOGGER.error(f"Read error: {e}")
                break

    async def _idle_checker(self):
        while self.connected:
            await asyncio.sleep(1)
            current_time = asyncio.get_event_loop().time()
            if (
                current_time - self.last_activity > self.idle_timeout
                and self.command_queue.empty()
            ):
                await self.disconnect()

    async def stop(self):
        """Gracefully stop the API client."""
        if self.connection_task and not self.connection_task.done():
            self.connection_task.cancel()
        await self.disconnect()


# Usage example
async def main():
    logging.basicConfig(level=logging.DEBUG)
    # Replace 'your_device_ip' with the actual IP address of your Heytech device
    client = HeytechTelnetClient("10.0.1.6")

    # Send commands
    # await client.send_command('smn\r\n')
    # await client.send_command('sop')
    positions = await client.async_get_shutter_positions()
    _LOGGER.info("positions %s", positions)

    shutters = await client.async_get_data()
    _LOGGER.info("shutters %s", shutters)
    # Process output
    # async for output_line in client.get_output():
    #     _LOGGER.info(f"Received: {output_line}")

    # Wait for a while to allow for idle timeout
    await asyncio.sleep(15)

    # Close the client explicitly if needed
    await client.stop()


if __name__ == "__main__":
    asyncio.run(main())

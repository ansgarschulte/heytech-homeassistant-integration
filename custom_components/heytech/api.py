"""
Heytech API Client.

This module provides an API client for interacting with Heytech devices without using external libraries.
"""

import asyncio
import logging
from asyncio import Queue
from typing import Any

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
MAX_RETRIES = 3  # Maximum number of retries for sending commands
RETRY_DELAY = 1  # Delay between retries in seconds


class IntegrationHeytechApiClientError(Exception):
    """Exception to indicate a general API error."""


class IntegrationHeytechApiClientCommunicationError(IntegrationHeytechApiClientError):
    """Exception to indicate a communication error."""

    def __str__(self) -> str:
        """Return a string representation of the error."""
        if self.__cause__:
            return f"Error communicating with Heytech device: {self.__cause__}"
        return "Error communicating with Heytech device"


class HeytechApiClient:
    def __init__(self, host: str, port: int = 1002, pin: str = "", idle_timeout=10):
        self._pin = pin
        self.host = host
        self.port = int(port)
        self.idle_timeout = idle_timeout
        self.command_queue: Queue[str] = Queue()
        self.connected = False
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.last_activity: float = 0.0
        self.connection_task: asyncio.Task | None = None
        self.read_task: asyncio.Task | None = None
        self.idle_task: asyncio.Task | None = None
        self.max_channels: int | None = None
        self.shutter_positions: dict[int, int] = {}
        self.shutters: dict[Any, dict[str, int]] = {}
        self._reconnecting = False

    async def connect(self):
        retries = 0
        while not self.connected and retries < MAX_RETRIES:
            try:
                _LOGGER.debug(f"Attempting to connect to {self.host}:{self.port}")
                self.reader, self.writer = await asyncio.open_connection(
                    self.host, self.port
                )
                self.connected = True
                self.last_activity = asyncio.get_event_loop().time()
                self.read_task = asyncio.create_task(self._read_output())
                self.idle_task = asyncio.create_task(self._idle_checker())
                _LOGGER.debug(
                    "Connected to Heytech device at %s:%s", self.host, self.port
                )
            except Exception as e:
                retries += 1
                _LOGGER.error(f"Connection error: {e}. Retry {retries}/{MAX_RETRIES}")
                await asyncio.sleep(RETRY_DELAY)
        if not self.connected:
            _LOGGER.error(
                f"Failed to connect to Heytech device after {MAX_RETRIES} retries."
            )
            raise IntegrationHeytechApiClientCommunicationError(
                "Failed to connect to Heytech device"
            )

    async def disconnect(self):
        if self.connected:
            _LOGGER.debug("Disconnecting from Heytech device")
            if self.read_task:
                self.read_task.cancel()
                self.read_task = None
            if self.idle_task:
                self.idle_task.cancel()
                self.idle_task = None
            if self.connection_task:
                self.connection_task.cancel()
                self.connection_task = None
            if self.writer:
                self.writer.close()
                try:
                    await asyncio.shield(self.writer.wait_closed())
                except asyncio.CancelledError:
                    _LOGGER.debug("CancelledError caught during wait_closed()")
                    # Optionally re-raise if you want the cancellation to propagate
                    # raise
                except Exception as e:
                    _LOGGER.error(f"Error while closing the connection: {e}")
                self.writer = None
            self.reader = None
            self.connected = False
            _LOGGER.debug("Disconnected from Heytech device")

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
                        "rhi\r\n",
                        "\r\n",
                        "rhb\r\n",
                        f"{channel}\r\n",
                        f"{shutter_command}\r\n",
                        "\r\n",
                        "rhe\r\n",
                        "\r\n",
                    ]
                )

        return commands

    async def add_shutter_command(self, action: str, channels: list[int]) -> None:
        """Add commands to the queue and process them."""
        commands = self._generate_shutter_command(action, channels)
        _LOGGER.debug("Adding commands to queue: %s", commands)
        for command in commands:
            await self.command_queue.put(command)
        if self.connection_task is None or self.connection_task.done():
            self.connection_task = asyncio.create_task(self._process_commands())

    async def async_test_connection(self) -> None:
        """Test connection to the API."""
        try:
            await self.connect()
            # Send a simple command to test the connection
            await self.add_shutter_command("sti", [])
            _LOGGER.debug("Connection test command sent successfully")
        except Exception as exc:
            raise IntegrationHeytechApiClientCommunicationError from exc

    async def async_get_data(self) -> dict[Any, dict[str, int]]:
        """Send 'smc' and 'smn' commands to fetch shutters data."""
        try:
            self.shutters = {}
            self.max_channels = None
            await self.add_shutter_command("smc", [])
            await self.add_shutter_command("smn", [])

            max_wait = 50
            while not self.max_channels and max_wait > 0:
                await asyncio.sleep(0.1)
                max_wait -= 1

            max_wait = 50
            while len(self.shutters) < (self.max_channels or 0) and max_wait > 0:
                await asyncio.sleep(0.1)
                max_wait -= 1

            if not self.shutters:
                raise IntegrationHeytechApiClientCommunicationError(
                    "Failed to retrieve shutters data"
                )

            return self.shutters
        except Exception as exc:
            _LOGGER.error("Failed to get data from Heytech API: %s", exc)
            raise IntegrationHeytechApiClientCommunicationError from exc

    async def async_get_shutter_positions(self) -> dict[int, int]:
        """Send 'sop' command and parse the shutter positions."""
        try:
            self.shutter_positions = {}
            await self.add_shutter_command("sop", [])
            # Wait for the 'sop' command to be processed
            max_wait = 50
            while not self.shutter_positions and max_wait > 0:
                await asyncio.sleep(0.1)
                max_wait -= 1

            if not self.shutter_positions:
                raise IntegrationHeytechApiClientCommunicationError(
                    "Failed to retrieve shutter positions"
                )

            _LOGGER.debug("Returning shutter positions: %s", self.shutter_positions)
            return self.shutter_positions
        except Exception as exc:
            _LOGGER.error("Failed to get shutter positions: %s", exc)
            raise IntegrationHeytechApiClientCommunicationError from exc

    async def _process_commands(self):
        while not self.command_queue.empty():
            command = await self.command_queue.get()
            retries = 0
            while retries < MAX_RETRIES:
                if not self.connected:
                    try:
                        await self.connect()
                    except IntegrationHeytechApiClientCommunicationError:
                        retries += 1
                        _LOGGER.error(f"Retrying to connect ({retries}/{MAX_RETRIES})")
                        await asyncio.sleep(RETRY_DELAY)
                        continue
                try:
                    if self.writer:
                        _LOGGER.debug("Sending command: %s", command.strip())
                        self.writer.write(command.encode("ascii"))
                        await self.writer.drain()
                        self.last_activity = asyncio.get_event_loop().time()
                        await asyncio.sleep(COMMAND_DELAY)
                        break  # Command sent successfully, break out of retry loop
                    _LOGGER.error("Writer is not available. Cannot send command.")
                    raise IntegrationHeytechApiClientCommunicationError(
                        "Writer is not available"
                    )
                except (
                    ConnectionResetError,
                    BrokenPipeError,
                    IntegrationHeytechApiClientCommunicationError,
                ) as e:
                    retries += 1
                    _LOGGER.error(
                        f"Error sending command: {e}. Retry {retries}/{MAX_RETRIES}"
                    )
                    await self.disconnect()
                    await asyncio.sleep(RETRY_DELAY)
                except Exception as e:
                    _LOGGER.error(f"Unexpected error sending command: {e}")
                    await self.disconnect()
                    raise
            else:
                _LOGGER.error(f"Failed to send command after {MAX_RETRIES} retries.")
                # Decide whether to continue or raise an exception
                # For now, we continue to the next command
                continue
        self.connection_task = None

    async def _read_output(self):
        while self.connected and self.reader:
            try:
                line_bytes = await self.reader.readline()
                if line_bytes == b"":  # EOF
                    _LOGGER.debug("EOF received from device")
                    # Connection may have been closed by the device
                    await self.disconnect()
                    break
                line = line_bytes.decode("ascii").strip()
                _LOGGER.debug("Received line: %s", line)
                if START_SOP in line and END_SOP in line:
                    self.shutter_positions = parse_shutter_positions(line)
                elif START_SMN in line and END_SMN in line:
                    one_shutter = parse_smn_output(line)
                    self.shutters = {**self.shutters, **one_shutter}
                elif START_SMC in line and END_SMC in line:
                    self.max_channels = parse_smc_output(line)
            except asyncio.CancelledError:
                _LOGGER.debug("Read task cancelled")
                break
            except (ConnectionResetError, asyncio.IncompleteReadError) as e:
                _LOGGER.error(f"Connection lost during reading: {e}")
                await self.disconnect()
                # Optionally attempt to reconnect
                await asyncio.sleep(RETRY_DELAY)
                try:
                    await self.connect()
                except IntegrationHeytechApiClientCommunicationError:
                    _LOGGER.error("Failed to reconnect during reading")
                    break
            except Exception as e:
                _LOGGER.error(f"Read error: {e}")
                await self.disconnect()
                break

    async def _idle_checker(self):
        while self.connected:
            await asyncio.sleep(1)
            current_time = asyncio.get_event_loop().time()
            if (
                current_time - self.last_activity > self.idle_timeout
                and self.command_queue.empty()
            ):
                _LOGGER.debug("Idle timeout reached, disconnecting")
                await self.disconnect()

    async def stop(self):
        """Gracefully stop the API client."""
        if self.connection_task and not self.connection_task.done():
            self.connection_task.cancel()
            self.connection_task = None
        await self.disconnect()


# Usage example (for testing purposes)
async def main():
    logging.basicConfig(level=logging.DEBUG)
    # Replace 'your_device_ip' with the actual IP address of your Heytech device
    client = HeytechApiClient("10.0.1.6", pin="your_pin")

    try:
        # Test connection
        await client.async_test_connection()

        # Get shutter positions
        positions = await client.async_get_shutter_positions()
        _LOGGER.info("Shutter positions: %s", positions)

        # Get shutters data
        shutters = await client.async_get_data()
        _LOGGER.info("Shutters data: %s", shutters)

        # Example: Open shutters on channels 3 and 5
        await client.add_shutter_command("100", [3, 4])

        # Wait for commands to be processed
        await asyncio.sleep(2)

        # Simulate idle timeout by waiting longer than idle_timeout
        await asyncio.sleep(client.idle_timeout + 5)

        # After idle timeout, add another command to test reconnection
        await client.add_shutter_command("up", [3, 4])

        # Wait for commands to be processed
        await asyncio.sleep(2)

    finally:
        # Close the client explicitly if needed
        await client.stop()


if __name__ == "__main__":
    asyncio.run(main())

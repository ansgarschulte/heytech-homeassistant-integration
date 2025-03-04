"""
Heytech API Client.

This module provides an API client for interacting with Heytech devices
without using external libraries.
"""

import asyncio
import logging
from asyncio import Queue
from typing import Any

from custom_components.heytech.parse_helper import (
    END_SKD,
    END_SMC,
    END_SMN,
    END_SOP,
    START_SKD,
    START_SMC,
    START_SMN,
    START_SOP,
    parse_skd_climate_data,
    parse_smc_max_channel_output,
    parse_smn_motor_names_output,
    parse_sop_shutter_positions,
)

_LOGGER = logging.getLogger(__name__)

COMMAND_DELAY = 0.05
MAX_RETRIES = 3  # Maximum number of retries for sending commands
RETRY_DELAY = 1  # Delay between retries in seconds
FULLY_OPEN = 100
FULLY_CLOSED = 0

SOP_INTERVAL = 60  # seconds
SKD_INTERVAL = 120  # seconds


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
    """Client for interacting with Heytech devices."""

    def __init__(
        self, host: str, port: int = 1002, pin: str = "", idle_timeout: int = 10
    ) -> None:
        """
        Initialize the API client.

        :param host: Device IP address.
        :param port: Port to connect to.
        :param pin: PIN for authentication (optional).
        :param idle_timeout: Idle timeout in seconds.
        """
        self._pin = pin
        self.host = host
        self.port = int(port)
        self.idle_timeout = idle_timeout
        # High priority commands (normal shutter commands)
        self.command_queue: Queue[list[str]] = Queue()
        # Low priority periodic commands
        self.periodic_command_queue: Queue[list[str]] = Queue()

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
        self.climate_data: dict[str, float] = {}
        self._reconnecting = False

        self.periodic_task = asyncio.create_task(self._periodic_commands())

    async def connect(self) -> None:
        """Connect to the Heytech device."""
        retries = 0
        while not self.connected and retries < MAX_RETRIES:
            try:
                _LOGGER.debug("Attempting to connect to %s:%s", self.host, self.port)
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
            except OSError:
                retries += 1
                _LOGGER.exception("Connection error. Retry %d/%d", retries, MAX_RETRIES)
                await asyncio.sleep(RETRY_DELAY)
        if not self.connected:
            _LOGGER.error(
                "Failed to connect to Heytech device after %d retries.", MAX_RETRIES
            )
            message = "Failed to connect to Heytech device"
            raise IntegrationHeytechApiClientCommunicationError(message)

    async def disconnect(self) -> None:
        """Disconnect from the Heytech device."""
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
                except Exception:
                    _LOGGER.exception("Error while closing the connection")
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
        elif action.isdigit():
            action_value = int(action)
            if action_value == FULLY_CLOSED:
                shutter_command = "down"
            elif action_value == FULLY_OPEN:
                shutter_command = "up"
            else:
                shutter_command = action
        else:
            shutter_command = action

        commands: list[str] = []

        if self._pin:
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

    async def add_command(self, action: str, channels: list[int]) -> None:
        """Add normal (high priority) commands to the queue."""
        commands = self._generate_shutter_command(action, channels)
        _LOGGER.debug("Adding commands to queue: %s", commands)
        await self.command_queue.put(commands)
        if self.connection_task is None or self.connection_task.done():
            self.connection_task = asyncio.create_task(self._process_commands())

    async def _add_periodic_command(self, action: str, channels: list[int]) -> None:
        """Add periodic (low priority) commands to the queue."""
        commands = self._generate_shutter_command(action, channels)
        _LOGGER.debug("Adding periodic command to queue: %s", commands)
        await self.periodic_command_queue.put(commands)
        if self.connection_task is None or self.connection_task.done():
            self.connection_task = asyncio.create_task(self._process_commands())

    async def async_test_connection(self) -> None:
        """Test connection to the API."""
        try:
            await self.connect()
            await self.add_command("sti", [])
            _LOGGER.debug("Connection test command sent successfully")
        except Exception as exc:
            _LOGGER.exception("Test connection failed")
            raise IntegrationHeytechApiClientCommunicationError from exc

    async def async_read_shutters_positions(self) -> dict[int, int]:
        """Send 'sop' command to fetch shutter positions."""
        try:
            await self.add_command("sop", [])
            max_wait = 50
            while not self.shutter_positions and max_wait > 0:
                await asyncio.sleep(0.1)
                max_wait -= 1

            if not self.shutter_positions:
                self._raise_communication_error("Failed to retrieve shutter positions")
            else:
                return self.shutter_positions
        except Exception as exc:
            _LOGGER.exception("Failed to get data from Heytech API")
            raise IntegrationHeytechApiClientCommunicationError from exc

    async def async_read_heytech_data(self) -> dict[Any, dict[str, int]]:
        """Send 'smc' and 'smn' commands to fetch shutters data."""
        try:
            await self.add_command("smc", [])
            await self.add_command("smn", [])
            await self.add_command("sop", [])
            await self.add_command("skd", [])

            max_wait = 50
            while not self.max_channels and max_wait > 0:
                await asyncio.sleep(0.1)
                max_wait -= 1
            max_wait = 50
            while len(self.shutters) < (self.max_channels or 0) and max_wait > 0:
                await asyncio.sleep(0.1)
                max_wait -= 1
            if not self.shutters:
                self._raise_communication_error("Failed to retrieve shutters data")
            await self.async_read_shutters_positions()
            await self.async_get_climate_data()
        except Exception as exc:
            _LOGGER.exception("Failed to get data from Heytech API")
            raise IntegrationHeytechApiClientCommunicationError from exc
        else:
            return self.shutters

    def get_shutter_positions(self) -> dict[int, int]:
        """Return the latest shutter positions."""
        return self.shutter_positions

    async def async_wait_for_shutter_positions(self) -> dict[int, int]:
        """Wait for shutter positions."""
        max_wait = 20
        while not self.shutter_positions and max_wait > 0:
            await asyncio.sleep(0.5)
            max_wait -= 1
        return self.shutter_positions

    def get_climate_data(self) -> dict[str, float]:
        """Return the latest climate data."""
        return self.climate_data

    async def async_get_climate_data(self) -> dict[str, float]:
        """Wait for climate data."""
        max_wait = 20
        while not self.climate_data and max_wait > 0:
            await asyncio.sleep(0.5)
            max_wait -= 1
        return self.climate_data

    def _raise_communication_error(self, message: str) -> None:
        """Raise a communication error with the given message."""
        raise IntegrationHeytechApiClientCommunicationError(message)

    async def _periodic_commands(self) -> None:
        """Send 'sop' command every x sec and 'skd' command every y (y>x) minutes."""
        last_skd = asyncio.get_event_loop().time()
        while True:
            now = asyncio.get_event_loop().time()
            # Send 'sop' every SOP_INTERVAL seconds
            await asyncio.sleep(SOP_INTERVAL)
            if not self.connected:
                await self.connect()
            await self._add_periodic_command("sop", [])

            # Check if it's time to send 'skd'
            if now - last_skd >= SKD_INTERVAL and self.connected:
                await self._add_periodic_command("skd", [])
                last_skd = asyncio.get_event_loop().time()

    async def _process_commands(self) -> None:
        """Process commands from the queues, prioritizing normal commands."""
        while not (self.command_queue.empty() and self.periodic_command_queue.empty()):
            # Always check the normal command queue first.
            if not self.command_queue.empty():
                commands = await self.command_queue.get()
            else:
                # If normal command queue is empty, process periodic commands.
                commands = await self.periodic_command_queue.get()

            retries = 0
            while retries < MAX_RETRIES:
                if not self.connected:
                    try:
                        await self.connect()
                    except IntegrationHeytechApiClientCommunicationError:
                        retries += 1
                        _LOGGER.exception(
                            "Retrying to connect (%d/%d)", retries, MAX_RETRIES
                        )
                        await asyncio.sleep(RETRY_DELAY)
                        continue
                try:
                    if self.writer:
                        for command in commands:
                            _LOGGER.debug("Sending command: %s", command.strip())
                            self.writer.write(command.encode("ascii"))
                            await self.writer.drain()
                            self.last_activity = asyncio.get_event_loop().time()
                            await asyncio.sleep(COMMAND_DELAY)
                        break
                    _LOGGER.error("Writer is not available. Cannot send command.")
                    self._raise_communication_error("Writer is not available")
                except (
                    ConnectionResetError,
                    BrokenPipeError,
                    IntegrationHeytechApiClientCommunicationError,
                ):
                    retries += 1
                    _LOGGER.exception(
                        "Error sending command. Retry %d/%d", retries, MAX_RETRIES
                    )
                    await self.disconnect()
                    await asyncio.sleep(RETRY_DELAY)
                except Exception:
                    _LOGGER.exception("Unexpected error sending command")
                    await self.disconnect()
                    raise
            else:
                _LOGGER.error("Failed to send command after %d retries.", MAX_RETRIES)

        self.connection_task = None

    async def _read_output(self) -> None:
        """Read output from the Heytech device."""
        while self.connected and self.reader:
            try:
                line_bytes = await self.reader.readline()
                if line_bytes == b"":  # EOF
                    _LOGGER.debug("EOF received from device")
                    await self.disconnect()
                    break
                line = line_bytes.decode("latin-1", errors="replace").strip()
                _LOGGER.debug("Received line: %s", line)
                if START_SOP in line and END_SOP in line:
                    self.shutter_positions = parse_sop_shutter_positions(line)
                elif START_SMN in line and END_SMN in line:
                    one_shutter = parse_smn_motor_names_output(line)
                    self.shutters = {**self.shutters, **one_shutter}
                elif START_SMC in line and END_SMC in line:
                    self.max_channels = parse_smc_max_channel_output(line)
                elif START_SKD in line and END_SKD in line:
                    self.climate_data = parse_skd_climate_data(line)
            except asyncio.CancelledError as e:
                _LOGGER.debug("Read task cancelled: %s", e)
                await self.disconnect()
                break
            except (ConnectionResetError, asyncio.IncompleteReadError):
                _LOGGER.exception("Connection lost during reading")
                await self.disconnect()
                await asyncio.sleep(RETRY_DELAY)
                try:
                    await self.connect()
                except IntegrationHeytechApiClientCommunicationError:
                    _LOGGER.exception("Failed to reconnect during reading")
                    break
            except Exception:
                _LOGGER.exception("Read error")
                await self.disconnect()
                break

    async def _idle_checker(self) -> None:
        """Check for idle timeout and disconnect if idle."""
        while self.connected:
            await asyncio.sleep(1)
            current_time = asyncio.get_event_loop().time()
            if (
                current_time - self.last_activity > self.idle_timeout
                and self.command_queue.empty()
                and self.periodic_command_queue.empty()
            ):
                _LOGGER.debug("Idle timeout reached, disconnecting")
                await self.disconnect()

    async def stop(self) -> None:
        """Gracefully stop the API client."""
        if self.connection_task and not self.connection_task.done():
            self.connection_task.cancel()
            self.connection_task = None
        await self.disconnect()
        if self.periodic_task:
            self.periodic_task.cancel()
            self.periodic_task = None


# Usage example (for testing purposes)
async def main() -> None:
    """Run the main function to test the Heytech API client."""
    logging.basicConfig(level=logging.DEBUG)
    client = HeytechApiClient("10.0.1.6", pin="")

    try:
        await client.async_read_heytech_data()

        positions = await client.async_wait_for_shutter_positions()
        _LOGGER.info("Shutter positions: %s", positions)
        positions = client.get_shutter_positions()
        _LOGGER.info("Shutter positions: %s", positions)
        climate_data = client.get_climate_data()
        _LOGGER.info("Climate data: %s", climate_data)

        # Normal commands will have priority over the periodic "sop" and "skd" commands.
        await client.add_command("100", [3, 4])
        await asyncio.sleep(30)
        positions = client.get_shutter_positions()
        _LOGGER.info("Shutter positions: %s", positions)

    finally:
        await client.stop()


if __name__ == "__main__":
    asyncio.run(main())

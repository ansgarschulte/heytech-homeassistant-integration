# api.py

from __future__ import annotations

import asyncio
import logging
import re

_LOGGER = logging.getLogger(__name__)

COMMAND_DELAY = 0.05  # Delay between commands in seconds

# Define the maximum number of channels supported by your Heytech system
MAX_CHANNELS = 32

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
        self.shutter_positions: dict[int, int] = {}  # Stores current positions

    def _generate_shutter_command(self, action: str, channels: list[int]) -> list[str]:
        """Generate shutter commands based on action and channels."""
        command_map = {
            "open": "up",
            "close": "down",
            "stop": "off",
            "sss": "sss",
            "smn": "smn",
        }

        if action.isdigit():
            shutter_command = action
        else:
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
                elif command.strip() == "sop":
                    await self._listen_for_sop_output(reader)

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
        except (
                asyncio.IncompleteReadError,
                asyncio.LimitOverrunError,
                asyncio.StreamReaderProtocolError,
        ):
            _LOGGER.exception("Error while parsing smn output")

    async def _listen_for_sop_output(self, reader: asyncio.StreamReader) -> None:
        """Listen and parse the output of the 'sop' command."""
        try:
            data = b''
            while b'ende_sop' not in data:
                chunk = await reader.read(100)
                if not chunk:
                    break
                data += chunk

            line = data.decode("ascii").strip()

            # Handle responses with and without 'start_sop'
            start_sop = "start_sop"
            end_sop = "ende_sop"

            if start_sop in line and end_sop in line:
                # Extract positions between 'start_sop' and 'ende_sop'
                start_index = line.find(start_sop) + len(start_sop)
                end_index = line.rfind(end_sop)
                positions_str = line[start_index:end_index]
            elif end_sop in line:
                # No 'start_sop', assume positions start at beginning
                positions_str = line.split(end_sop)[0].strip(",")
            else:
                _LOGGER.error("Unexpected 'sop' response: %s", line)
                self.shutter_positions = {}
                return

            positions_list = positions_str.split(",")
            positions = {}
            for idx, pos in enumerate(positions_list, start=1):
                if idx > MAX_CHANNELS:
                    _LOGGER.debug("Ignoring position for channel %d as it exceeds MAX_CHANNELS (%d)", idx, MAX_CHANNELS)
                    break  # Stop processing further channels

                pos = pos.strip()  # Remove any leading/trailing whitespace

                if not pos:
                    _LOGGER.debug("Empty position for channel %d, assigning 0", idx)
                    positions[idx] = 0
                    continue
                try:
                    position_value = int(pos)
                    if 0 <= position_value <= 100:
                        positions[idx] = position_value
                    else:
                        _LOGGER.warning("Position value '%s' for channel %d is out of range (0-100). Assigning 0.", pos, idx)
                        positions[idx] = 0  # Default to 0% if out of range
                except ValueError:
                    _LOGGER.warning("Invalid position value '%s' for channel %d", pos, idx)
                    positions[idx] = 0  # Default to 0% if invalid
            self.shutter_positions = positions
            _LOGGER.debug("Parsed shutter positions: %s", positions)
        except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, asyncio.StreamReaderProtocolError) as e:
            _LOGGER.exception("Error while parsing sop output")
            self.shutter_positions = {}

    async def async_test_connection(self) -> None:
        """Test connection to the API."""
        await self.add_shutter_command("sss", [])

    async def async_get_data(self) -> None:
        """Send 'smn' command to fetch shutters data."""
        await self.add_shutter_command("smn", [])

    async def async_get_shutter_positions(self) -> dict[int, int]:
        """Send 'sop' command and parse the shutter positions."""
        async with self._lock:
            commands = ["sop\r\n"]
            self._queue.extend(commands)
            if not self._processing:
                self._processing = True
                await self._process_queue()
                self._processing = False

            return self.shutter_positions
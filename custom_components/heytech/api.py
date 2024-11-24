# api.py

from __future__ import annotations
import asyncio
import logging
import re

_LOGGER = logging.getLogger(__name__)

COMMAND_DELAY = 0.05  # Delay between commands in seconds
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
        self.shutters = {}  # Stores the parsed shutters
        self.shutter_positions: dict[int, int] = {}  # Stores current positions

        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._listen_task: asyncio.Task | None = None
        self._reconnect_delay = 5  # seconds

        self._connection_lock = asyncio.Lock()
        self._stop_event = asyncio.Event()

        # Initialize connection state
        self._connected = False

        # Event to signal 'sop' response received
        self._sop_event = asyncio.Event()

    def _generate_shutter_command(self, action: str, channels: list[int]) -> list[str]:
        """Generate shutter commands based on action and channels."""
        command_map = {
            "open": "up",
            "close": "down",
            "stop": "off",
            "sss": "sss",
            "smn": "smn",
            "sop": "sop",  # Ensure 'sop' is correctly mapped
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

        if action in ["smn", "sop"]:
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

    async def connect(self) -> None:
        """Establish a connection to the Heytech hub and start listening."""
        async with self._connection_lock:
            if self._writer:
                _LOGGER.debug("Already connected to Heytech hub.")
                return  # Already connected

            try:
                _LOGGER.info("Connecting to Heytech hub at %s:%s", self._host, self._port)
                self._reader, self._writer = await asyncio.open_connection(self._host, self._port)
                self._connected = True
                _LOGGER.info("Successfully connected to Heytech hub.")
                # Start the background listener
                self._listen_task = asyncio.create_task(self._listen())
                # If a PIN is set, send it
                if self._pin:
                    _LOGGER.debug("Sending PIN to Heytech hub.")
                    await self._send_commands(["rsc\r\n", f"{self._pin}\r\n"])
                # Send the 'smn' command to discover shutters
                _LOGGER.debug("Sending 'smn' command to discover shutters.")
                await self._send_commands(["smn\r\n"])
            except Exception as e:
                _LOGGER.error("Failed to connect to Heytech hub: %s", e)
                raise IntegrationHeytechApiClientCommunicationError from e

    async def disconnect(self) -> None:
        """Close the connection to the Heytech hub."""
        async with self._connection_lock:
            if self._listen_task:
                self._listen_task.cancel()
                try:
                    await self._listen_task
                except asyncio.CancelledError:
                    _LOGGER.debug("Listener task cancelled.")
                except Exception as e:
                    _LOGGER.error("Error while cancelling listener task: %s", e)
                self._listen_task = None

            if self._writer:
                _LOGGER.info("Closing connection to Heytech hub.")
                self._writer.close()
                try:
                    await self._writer.wait_closed()
                except Exception as e:
                    _LOGGER.warning("Error while closing connection: %s", e)
                self._writer = None
                self._reader = None
                self._connected = False

    # api.py

    async def _listen(self) -> None:
        """Continuously listen for incoming data from the hub."""
        try:
            while not self._stop_event.is_set():
                try:
                    line = await self._reader.readline()
                    if not line:
                        _LOGGER.warning("Connection closed by Heytech hub.")
                        await self._handle_disconnection()
                        break

                    decoded_line = line.decode("ascii").strip()
                    _LOGGER.debug("Received line: %s", decoded_line)

                    if "sop" in decoded_line:
                        await self._parse_sop(decoded_line)
                        # Signal that 'sop' response has been processed
                        self._sop_event.set()
                    elif "smn" in decoded_line:
                        await self._parse_smn(decoded_line)
                    # Handle other unsolicited responses here

                except asyncio.CancelledError:
                    _LOGGER.debug("Listener task received cancellation.")
                    break  # Exit the loop to allow task to finish
                except Exception as e:
                    _LOGGER.exception("Error while listening to Heytech hub: %s", e)
                    await self._handle_disconnection()
                    break
        except asyncio.CancelledError:
            _LOGGER.debug("Listener task cancelled.")
        except Exception as e:
            _LOGGER.exception("Unexpected error in listener task: %s", e)

    # api.py

    async def _parse_smn(self, line: str) -> None:
        """Parse the 'smn' response and discover shutters."""
        try:
            # Example response format: 'smn:1,2,3,4,5\r\n'
            if line.startswith("smn:"):
                shutters_str = line[len("smn:"):].strip()
                shutter_ids = [int(shutter_id) for shutter_id in shutters_str.split(",") if shutter_id.isdigit()]
                self.shutters = {shutter_id: {"id": shutter_id} for shutter_id in shutter_ids}
                _LOGGER.debug("Discovered shutters: %s", self.shutters)
            else:
                _LOGGER.error("Unexpected 'smn' response format: %s", line)
        except Exception as e:
            _LOGGER.exception("Error while parsing 'smn' response: %s", e)

    async def _handle_disconnection(self) -> None:
        """Handle unexpected disconnections and attempt reconnection."""
        await self.disconnect()
        _LOGGER.info("Attempting to reconnect to Heytech hub in %s seconds...", self._reconnect_delay)
        await asyncio.sleep(self._reconnect_delay)
        try:
            await self.connect()
        except IntegrationHeytechApiClientCommunicationError:
            _LOGGER.error("Reconnection attempt failed.")
            # Schedule another reconnection attempt
            asyncio.create_task(self._handle_disconnection())

    async def _parse_sop(self, line: str) -> None:
        """Parse the 'sop' response and update shutter positions."""
        try:
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
                return

            positions_list = positions_str.split(",")
            positions = {}
            for idx, pos in enumerate(positions_list, start=1):
                if idx > MAX_CHANNELS:
                    _LOGGER.debug("Ignoring position for channel %d as it exceeds MAX_CHANNELS (%d)", idx, MAX_CHANNELS)
                    break  # Stop processing further channels

                pos = pos.strip()  # Remove any leading/trailing whitespace

                _LOGGER.debug("Parsing position for channel %d: '%s'", idx, pos)

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
        except Exception as e:
            _LOGGER.exception("Error while parsing 'sop' response: %s", e)

    async def _send_commands(self, commands: list[str]) -> None:
        """Send a list of commands to the hub."""
        if not self._writer:
            _LOGGER.error("Not connected to Heytech hub.")
            raise IntegrationHeytechApiClientCommunicationError("Not connected to Heytech hub.")

        for command in commands:
            try:
                self._writer.write(command.encode("ascii"))
                await self._writer.drain()
                _LOGGER.debug("Sent command: %s", command.strip())
                await asyncio.sleep(COMMAND_DELAY)
            except Exception as e:
                _LOGGER.error("Error sending command '%s': %s", command.strip(), e)
                raise IntegrationHeytechApiClientCommunicationError("Error sending commands") from e

    async def add_shutter_command(self, action: str, channels: list[int]) -> None:
        """Add shutter commands to be sent to the hub."""
        try:
            commands = self._generate_shutter_command(action, channels)
            await self._send_commands(commands)
        except Exception as e:
            _LOGGER.error("Failed to send shutter command: %s", e)
            raise IntegrationHeytechApiClientCommunicationError from e

    async def async_test_connection(self) -> None:
        """Test connection to the API by sending a test command."""
        try:
            _LOGGER.debug("Testing connection to Heytech hub.")
            await self.add_shutter_command("sss", [])
            _LOGGER.debug("Test command 'sss' sent successfully.")
        except IntegrationHeytechApiClientCommunicationError as e:
            _LOGGER.error("Test connection failed: %s", e)
            raise

    async def async_get_data(self) -> dict[int, int]:
        """Send 'sop' command and return the shutter positions."""
        # Reset the event before sending the command
        self._sop_event.clear()
        await self.add_shutter_command("sop", [])
        try:
            # Wait for the 'sop' response to be processed
            await asyncio.wait_for(self._sop_event.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout while waiting for 'sop' response.")
            raise IntegrationHeytechApiClientCommunicationError("Timeout waiting for 'sop' response.")
        return self.shutter_positions

    async def stop_listening(self) -> None:
        """Stop listening and disconnect."""
        self._stop_event.set()
        await self.disconnect()
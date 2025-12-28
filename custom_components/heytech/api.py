"""
Heytech API Client.

This module provides an API client for interacting with Heytech devices
without using external libraries.
"""

import asyncio
import logging
from asyncio import Queue
from datetime import datetime
from typing import Any

from custom_components.heytech.parse_helper import (
    END_RGZ,
    END_RZN,
    END_SAU,
    END_SBP,
    END_SJP,
    END_SKD,
    END_SLA,
    END_SLD,
    END_SMC,
    END_SMN,
    END_SOP,
    END_SRP,
    END_SWP,
    END_SZN,
    START_RGZ,
    START_RZN,
    START_SAU,
    START_SBP,
    START_SJP,
    START_SKD,
    START_SLA,
    START_SLD,
    START_SMC,
    START_SMN,
    START_SOP,
    START_SRP,
    START_SWP,
    START_SZN,
    parse_rgz_group_assignments,
    parse_sau_automation_status,
    parse_sbp_shading_params,
    parse_sgz_group_control_output,
    parse_sjp_jalousie_params,
    parse_skd_climate_data,
    parse_sla_logbook_count,
    parse_sld_logbook_entry,
    parse_smc_max_channel_output,
    parse_smn_motor_names_output,
    parse_sop_shutter_positions,
    parse_srp_rain_params,
    parse_swp_wind_params,
    parse_szn_scenario_names_output,
)

_LOGGER = logging.getLogger(__name__)

COMMAND_DELAY = 0.05
MAX_RETRIES = 3  # Maximum number of retries for sending commands
RETRY_DELAY = 1  # Delay between retries in seconds
FULLY_OPEN = 100
FULLY_CLOSED = 0

# Polling intervals - reduced for better responsiveness
# Position updates come from controller automatically when shutters move
SOP_INTERVAL = 120  # seconds - Poll position every 2 minutes (was 60)
SKD_INTERVAL = 300  # seconds - Poll climate every 5 minutes (was 120)

# Channel constants
SCENARIO_CHANNEL_START = 65  # Scenarios start at channel 65


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
        self.scenarios: dict[int, str] = {}  # Scenario number -> name
        self.groups: dict[int, dict[str, Any]] = {}  # Group number -> {name, channels}
        self.logbook_entries: list[dict[str, Any]] = []
        self.logbook_count: int = 0
        self.automation_status: bool | None = None
        self.jalousie_params: dict[int, dict[str, Any]] = {}  # Channel -> params
        self.shading_params: dict[int, dict[str, Any]] = {}  # Channel -> params
        self.wind_params: dict[int, dict[str, Any]] = {}  # Channel -> params
        self.rain_params: dict[int, dict[str, Any]] = {}  # Channel -> params
        self._reconnecting = False
        self._discovery_complete: asyncio.Event | None = None

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

                # Initialize controller (required after boot/restart)
                # Send RHI (Hand-Steuerung Initialisierung) + RHE sequence
                await self._send_initialization_sequence()
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

    async def _send_initialization_sequence(self) -> None:
        """
        Send initialization sequence to wake up controller.

        The HeyTech controller requires RHI (Hand-Steuerung Initialisierung)
        after boot/restart before it responds to regular commands.
        This is what the original HEYcontrol.exe does on connect.
        """
        if not self.writer:
            return

        try:
            _LOGGER.info("Sending controller initialization sequence (RHI/RHE)")
            init_commands = [
                "rhi\r\n",  # Hand-Steuerung Initialisierung
                "\r\n",
                "rhe\r\n",  # Hand-Steuerung exit
                "\r\n",
            ]

            for cmd in init_commands:
                self.writer.write(cmd.encode("utf-8"))
                await self.writer.drain()
                await asyncio.sleep(0.05)  # Small delay between commands

            _LOGGER.debug("Controller initialization sequence sent successfully")
        except Exception:
            _LOGGER.exception("Failed to send initialization sequence")

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
            # Reset discovery state before each run
            self.shutters = {}
            self.scenarios = {}
            self.max_channels = None
            self._discovery_complete = asyncio.Event()

            await self.add_command("smc", [])
            # Controller auto-iterates ALL channels including scenarios
            await self.add_command("smn", [])
            await self.add_command("sop", [])
            await self.add_command("skd", [])
            await self.add_command("sau", [])  # Get automation status
            await self.add_command("sgz", [])  # Get group info (bitmask format)
            await self.add_command("sla", [])  # Get logbook count
            await self.add_command("sjp", [])  # Get jalousie params (for all channels)
            await self.add_command("sbp", [])  # Get shading params
            await self.add_command("swp", [])  # Get wind params
            await self.add_command("srp", [])  # Get rain params

            # Wait for max_channels to be set
            max_wait = 50
            while not self.max_channels and max_wait > 0:
                await asyncio.sleep(0.1)
                max_wait -= 1

            if not self.max_channels:
                _LOGGER.warning(
                    "Failed to retrieve max_channels, falling back to timeout"
                )
                # Fallback: wait for stable count
                stable_cycles = 0
                last_count = -1
                max_stable_cycles = 15

                while stable_cycles < max_stable_cycles:
                    await asyncio.sleep(0.2)
                    if len(self.shutters) == last_count:
                        stable_cycles += 1
                    else:
                        stable_cycles = 0
                        last_count = len(self.shutters)
            else:
                # Event-based: wait until all shutters discovered or timeout
                try:
                    await asyncio.wait_for(
                        self._discovery_complete.wait(),
                        timeout=10.0
                    )
                    _LOGGER.debug(
                        "Discovery complete: %d/%d shutters found",
                        len(self.shutters),
                        self.max_channels
                    )
                except TimeoutError:
                    _LOGGER.warning(
                        "Discovery timeout: found %d shutters, "
                        "expected up to %d channels",
                        len(self.shutters),
                        self.max_channels,
                    )

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

    def get_scenarios(self) -> dict[int, str]:
        """Return the available scenarios."""
        return self.scenarios

    async def async_activate_scenario(self, scenario_number: int) -> None:
        """
        Activate a scenario by number.

        :param scenario_number: The scenario number to activate (1-based)
        """
        _LOGGER.info("Activating scenario %d", scenario_number)
        commands = []
        if self._pin:
            commands.extend(["rsc\r\n", f"{self._pin}\r\n"])
        commands.extend([
            "rsa\r\n",
            f"{scenario_number}\r\n",
        ])
        await self.command_queue.put(commands)
        if self.connection_task is None or self.connection_task.done():
            self.connection_task = asyncio.create_task(self._process_commands())

    def get_automation_status(self) -> bool | None:
        """Return the automation status (external switch state)."""
        return self.automation_status

    def get_groups(self) -> dict[int, dict[str, Any]]:
        """Return the available groups."""
        return self.groups

    async def async_control_group(self, group_number: int, action: str) -> None:
        """
        Control a group of shutters.

        :param group_number: The group number (1-based)
        :param action: Action to perform ('open', 'close', 'stop', or position 0-100)
        """
        _LOGGER.info("Controlling group %d with action %s", group_number, action)
        group = self.groups.get(group_number)
        if not group:
            _LOGGER.warning("Group %d not found", group_number)
            return

        channels = group.get("channels", [])
        if channels:
            await self.add_command(action, channels)
        else:
            _LOGGER.warning("Group %d has no channels assigned", group_number)

    def get_logbook_entries(self) -> list[dict[str, Any]]:
        """Return the logbook entries."""
        return self.logbook_entries

    def get_logbook_count(self) -> int:
        """Return the number of logbook entries."""
        return self.logbook_count

    async def async_read_logbook(self, max_entries: int = 50) -> list[dict[str, Any]]:
        """
        Read logbook entries from the device.

        :param max_entries: Maximum number of entries to read
        :return: List of logbook entries
        """
        self.logbook_entries = []

        # Request logbook entries
        for i in range(1, min(max_entries, self.logbook_count) + 1):
            commands = ["sld\r\n", f"{i}\r\n"]
            await self.command_queue.put(commands)

        if self.connection_task is None or self.connection_task.done():
            self.connection_task = asyncio.create_task(self._process_commands())

        # Wait for entries to be collected
        await asyncio.sleep(2)
        return self.logbook_entries

    async def async_clear_logbook(self) -> None:
        """Clear the logbook on the device."""
        _LOGGER.info("Clearing logbook")
        commands = ["sll\r\n"]
        if self._pin:
            commands = ["rsc\r\n", f"{self._pin}\r\n", *commands]
        await self.command_queue.put(commands)
        if self.connection_task is None or self.connection_task.done():
            self.connection_task = asyncio.create_task(self._process_commands())

    async def async_sync_time(self) -> None:
        """Synchronize date and time with the controller."""
        # Get current time in local timezone (controller expects local time)
        now = datetime.now().astimezone()

        # Format: rdt followed by: day,month,year,hour,minute,second,weekday
        # Weekday: 1=Monday, 7=Sunday
        weekday = now.isoweekday()  # 1=Monday, 7=Sunday

        time_data = (
            f"{now.day},{now.month},{now.year % 100},"
            f"{now.hour},{now.minute},{now.second},{weekday}"
        )

        _LOGGER.info("Syncing time: %s", time_data)

        commands = [f"rdt{time_data}\r\n"]
        if self._pin:
            commands = ["rsc\r\n", f"{self._pin}\r\n", *commands]

        await self.command_queue.put(commands)
        if self.connection_task is None or self.connection_task.done():
            self.connection_task = asyncio.create_task(self._process_commands())

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

            # Check if it's time to send 'skd' and 'sau'
            if now - last_skd >= SKD_INTERVAL and self.connected:
                await self._add_periodic_command("skd", [])
                await self._add_periodic_command("sau", [])
                last_skd = asyncio.get_event_loop().time()

    async def _process_commands(self) -> None:
        """
        Process commands from the queues, prioritizing normal commands.

        User commands have absolute priority - they interrupt periodic commands.
        This ensures responsive control even when periodic polling is active.
        """
        while not (self.command_queue.empty() and self.periodic_command_queue.empty()):
            # Always check the normal command queue first - PRIORITY!
            if not self.command_queue.empty():
                commands = await self.command_queue.get()
                is_user_command = True
            else:
                # Only process periodic commands when no user commands pending
                # Check if user command arrived while we were waiting
                try:
                    commands = self.periodic_command_queue.get_nowait()
                    is_user_command = False
                except asyncio.QueueEmpty:
                    # Both queues empty now
                    break

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
                            _LOGGER.debug(
                                "Sending %s command: %s",
                                "USER" if is_user_command else "periodic",
                                command.strip()
                            )
                            self.writer.write(command.encode("ascii"))
                            await self.writer.drain()
                            self.last_activity = asyncio.get_event_loop().time()

                            # Shorter delay for user commands = more responsive!
                            if is_user_command:
                                await asyncio.sleep(0.02)  # 20ms for user commands
                            else:
                                await asyncio.sleep(COMMAND_DELAY)  # 50ms for periodic
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

                    # Check if this is a scenario or a regular shutter
                    for name, data in one_shutter.items():
                        channel = data["channel"]
                        if channel >= SCENARIO_CHANNEL_START:
                            # This is a scenario, not a shutter
                            scenario_num = channel - 64  # Scenarios start at 1
                            self.scenarios[scenario_num] = name.strip()
                            _LOGGER.info(
                                "Scenario discovered: %d. %s",
                                scenario_num,
                                name.strip(),
                            )
                        else:
                            # Regular shutter - merge with existing data
                            self.shutters[name] = {
                                "channel": channel,
                                "name": name,
                            }

                    # Signal discovery complete when all channels processed
                    if (self._discovery_complete
                        and self.max_channels
                        and len(self.shutters) >= self.max_channels):
                        self._discovery_complete.set()
                elif START_SMC in line and END_SMC in line:
                    self.max_channels = parse_smc_max_channel_output(line)
                elif START_SKD in line and END_SKD in line:
                    self.climate_data = parse_skd_climate_data(line)
                elif START_RZN in line and END_RZN in line:
                    # Parse scenario names from RZN (receive command)
                    one_scenario = parse_szn_scenario_names_output(line)
                    self.scenarios = {**self.scenarios, **one_scenario}
                    _LOGGER.info("Scenario discovered: %s", one_scenario)
                elif START_SZN in line and END_SZN in line:
                    # Fallback: also check SZN (though RZN is correct)
                    one_scenario = parse_szn_scenario_names_output(line)
                    self.scenarios = {**self.scenarios, **one_scenario}
                    _LOGGER.info("Scenario discovered via SZN: %s", one_scenario)
                elif START_SAU in line and END_SAU in line:
                    self.automation_status = parse_sau_automation_status(line)
                elif START_RGZ in line and END_RGZ in line:
                    # Parse group channel assignments from RGZ (receive command)
                    group_channels = parse_rgz_group_assignments(line)
                    for group_num, channels in group_channels.items():
                        if group_num not in self.groups:
                            # Generate a default name
                            self.groups[group_num] = {
                                "name": f"Group {group_num}",
                                "channels": channels
                            }
                        else:
                            self.groups[group_num]["channels"] = channels
                        _LOGGER.info(
                            "Group %d discovered with channels %s",
                            group_num,
                            channels,
                        )
                elif "start_sgz" in line and "ende_sgz" in line:
                    # Parse group info from SGZ
                    # (contains bitmasks for channel assignments)
                    group_data = parse_sgz_group_control_output(line)
                    for group_num, info in group_data.items():
                        self.groups[group_num] = info
                        _LOGGER.info(
                            "Group %d discovered: '%s' with channels %s",
                            group_num,
                            info.get("name"),
                            info.get("channels"),
                        )
                elif START_SLD in line and END_SLD in line:
                    # Parse logbook entry
                    entry = parse_sld_logbook_entry(line)
                    if entry:
                        self.logbook_entries.append(entry)
                elif START_SLA in line and END_SLA in line:
                    # Parse logbook count
                    self.logbook_count = parse_sla_logbook_count(line)
                elif START_SJP in line and END_SJP in line:
                    # Parse jalousie parameters
                    params = parse_sjp_jalousie_params(line)
                    if params:
                        channel = params.pop("channel")
                        self.jalousie_params[channel] = params
                elif START_SBP in line and END_SBP in line:
                    # Parse shading parameters
                    params = parse_sbp_shading_params(line)
                    if params:
                        channel = params.pop("channel")
                        self.shading_params[channel] = params
                elif START_SWP in line and END_SWP in line:
                    # Parse wind parameters
                    params = parse_swp_wind_params(line)
                    if params:
                        channel = params.pop("channel")
                        self.wind_params[channel] = params
                elif START_SRP in line and END_SRP in line:
                    # Parse rain parameters
                    params = parse_srp_rain_params(line)
                    if params:
                        channel = params.pop("channel")
                        self.rain_params[channel] = params
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

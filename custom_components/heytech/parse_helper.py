"""Helper Functions for parsing Heytech responses."""

import logging
import re
from typing import Any

_LOGGER = logging.getLogger(__name__)

# Define the maximum number of channels supported by your Heytech system
MAX_CHANNELS = 32

MAX_POSITION = 132
START_SOP = "start_sop"
END_SOP = "ende_sop"
START_SKD = "start_skd"
END_SKD = "ende_skd"
START_SMN = "start_smn"
END_SMN = "ende_smn"
START_SMC = "start_smc"
END_SMC = "ende_smc"
START_SMO = "start_smo"
END_SMO = "ende_smo"
START_SFI = "start_sfi"
END_SFI = "ende_sfi"
START_SZN = "start_szn"
END_SZN = "ende_szn"
START_RZN = "start_rzn"
END_RZN = "ende_rzn"
START_SSZ = "start_ssz"
END_SSZ = "ende_ssz"
START_SAU = "start_sau"
END_SAU = "ende_sau"
START_SGR = "start_sgr"
END_SGR = "ende_sgr"
START_RGZ = "start_rgz"
END_RGZ = "ende_rgz"
START_SLD = "start_sld"
END_SLD = "ende_sld"
START_SLA = "start_sla"
END_SLA = "ende_sla"
START_SJP = "start_sjp"
END_SJP = "ende_sjp"
START_SFS = "start_sfs"
END_SFS = "ende_sfs"
START_SBP = "start_sbp"
END_SBP = "ende_sbp"
START_SDM = "start_sdm"
END_SDM = "ende_sdm"
START_SDA = "start_sda"
END_SDA = "ende_sda"
START_SWP = "start_swp"
END_SWP = "ende_swp"
START_SRP = "start_srp"
END_SRP = "ende_srp"


def parse_sop_shutter_positions(line: str) -> dict[int, int]:
    """Handle responses with and without 'start_sop'."""
    if START_SOP in line and END_SOP in line:
        # Extract positions between 'start_sop' and 'ende_sop'
        start_index = line.find(START_SOP) + len(START_SOP)
        end_index = line.rfind(END_SOP)
        positions_str = line[start_index:end_index]
    elif END_SOP in line:
        # No 'start_sop', assume positions start at beginning
        positions_str = line.split(END_SOP)[0].strip(",")
    else:
        _LOGGER.error("Unexpected 'sop' response: %s", line)
        return {}

    positions_list = positions_str.split(",")
    positions = {}
    for idx, position in enumerate(positions_list, start=1):
        if idx > MAX_CHANNELS:
            break  # Stop processing further channels

        pos = position.strip()  # Remove any leading/trailing whitespace

        if not pos:
            _LOGGER.debug("Empty position for channel %d, assigning 0", idx)
            positions[idx] = 0
            continue
        try:
            position_value = int(pos)
            if 0 <= position_value <= MAX_POSITION:
                positions[idx] = position_value
            else:
                _LOGGER.warning(
                    "Position value '%s' for channel %d "
                    "is out of range (0-100). Assigning 0.",
                    pos,
                    idx,
                )
                positions[idx] = 0  # Default to 0% if out of range
        except ValueError:
            _LOGGER.warning("Invalid position value '%s' for channel %d", pos, idx)
            positions[idx] = 0  # Default to 0% if invalid
    return positions


def parse_skd_climate_data(line: str) -> dict[str, float]:
    """Get Climate data from the 'skd' command."""
    # Example response:
    # start_skd0,999,999,999,999,999,999,999,999,0,0,0,0,1,0,0,ende_skd
    if START_SKD in line and END_SKD in line:
        # Extract positions between 'start_sdk' and 'ende_sdk'
        start_index = line.find(START_SKD) + len(START_SKD)
        end_index = line.rfind(END_SKD)
        data_str = line[start_index:end_index]

        data_list = data_str.split(",")
        climate_data: dict[str, float] = {}
        data_list = [
            data.strip() for data in data_list
        ]  # Remove any leading/trailing whitespace
        data_list = [
            data if data != "999" else None for data in data_list
        ]  # Replace '999' with None
        data_list[16] = None  # Remove the last element 'ende_skd'
        data_list = [
            int(data) if data is not None else data for data in data_list
        ]  # Convert to int if not None

        climate_data["brightness"] = data_list[0]
        climate_data["indoor temperature"] = (
            float(f"{data_list[1]}.{data_list[2]}")
            if data_list[1] is not None and data_list[2] is not None
            else None
        )
        climate_data["indoor temperature min"] = data_list[3]
        climate_data["indoor temperature max"] = data_list[4]
        climate_data["outdoor temperature"] = (
            float(f"{int(data_list[5])}.{int(data_list[6])}")
            if data_list[5] is not None and data_list[6] is not None
            else None
        )
        climate_data["outdoor temperature min"] = data_list[7]
        climate_data["outdoor temperature max"] = data_list[8]
        climate_data["current wind speed"] = data_list[9]
        climate_data["current wind speed max"] = data_list[10]
        climate_data["alarm"] = data_list[11]
        climate_data["rain"] = data_list[12]
        climate_data["brightness medium"] = data_list[14]
        climate_data["relative humidity"] = data_list[15]
        return climate_data
    return {}


def parse_smn_motor_names_output(line: str) -> dict[Any, dict[str, int]]:
    """Listen and parse the output of the 'smn' command."""
    shutters = {}

    if START_SMN in line and END_SMN in line:
        match = re.match(r"start_smn(\d+),(.+?),(\d+),ende_smn", line)
        if match:
            channel = int(match.group(1))
            name = match.group(2).strip()
            shutters[name] = {"channel": channel}
    return shutters


def parse_smc_max_channel_output(line: str) -> int:
    """Parse the output of the 'smc' command."""
    if START_SMC in line and END_SMC in line:
        # Example response: 'start_smc32ende_smc'
        match = re.match(r"start_smc(\d+)ende_smc", line)
        if match:
            return int(match.group(1))
    return 0


def parse_smo_model_output(line: str) -> str:
    """Parse the output of the 'smo' command."""
    # Example response: 'start_smoHEYtech RS879M  ende_smo'
    return _parse_string_output(line, START_SMO, END_SMO)


def parse_sfi_model_output(line: str) -> str:
    """Parse the output of the 'sfi' command."""
    # Example response: 'start_sfi8.027rende_sfi
    return _parse_string_output(line, START_SFI, END_SFI)


def _parse_string_output(line: str, start_command: str, stop_command: str) -> str:
    """Parse the output of any string command."""
    if start_command in line and stop_command in line:
        match = re.match(rf"{start_command}(.+?){stop_command}", line)
        if match:
            return str(match.group(1))
    return "Unknown"


def parse_szn_scenario_names_output(line: str) -> dict[int, str]:
    """
    Parse scenario names from the 'szn' or 'rzn' command.

    Example response: 'start_rzn1,Scenario Name,1,ende_rzn'
    Returns dict with scenario number as key and name as value.

    Note: The correct receive command is RZN, not SZN!
    SZN is the send command, RZN is receive.
    """
    scenarios = {}

    # Try RZN first (correct receive command)
    if START_RZN in line and END_RZN in line:
        match = re.match(r"start_rzn(\d+),(.+?),(\d+),ende_rzn", line)
        if match:
            scenario_num = int(match.group(1))
            name = match.group(2).strip()
            scenarios[scenario_num] = name
            _LOGGER.debug("Parsed scenario %d: '%s'", scenario_num, name)
    # Fallback to SZN for backward compatibility
    elif START_SZN in line and END_SZN in line:
        match = re.match(r"start_szn(\d+),(.+?),(\d+),ende_szn", line)
        if match:
            scenario_num = int(match.group(1))
            name = match.group(2).strip()
            scenarios[scenario_num] = name
            _LOGGER.debug("Parsed scenario %d: '%s' (via SZN)", scenario_num, name)

    return scenarios


def parse_ssz_scenarios_output(line: str) -> dict[int, dict[str, Any]]:
    """
    Parse scenario configuration from the 'ssz' command.

    Example response: 'start_ssz1,50,60,70,...ende_ssz'
    Returns dict with scenario number and channel positions.
    """
    scenarios = {}
    if START_SSZ in line and END_SSZ in line:
        # Extract data between markers
        start_index = line.find(START_SSZ) + len(START_SSZ)
        end_index = line.rfind(END_SSZ)
        data_str = line[start_index:end_index]

        parts = data_str.split(",")
        if len(parts) > 0:
            try:
                scenario_num = int(parts[0])
                positions = [int(p) if p.strip().isdigit() else None
                           for p in parts[1:]]
                scenarios[scenario_num] = {
                    "positions": positions
                }
            except (ValueError, IndexError):
                _LOGGER.warning("Failed to parse scenario data: %s", line)
    return scenarios


def parse_sau_automation_status(line: str) -> bool | None:
    """
    Parse automation status from the 'sau' command.

    Example response: 'start_sau1ende_sau' (1=enabled, 0=disabled)
    Returns True if automation is enabled, False if disabled, None on error.
    """
    if START_SAU in line and END_SAU in line:
        match = re.match(r"start_sau(\d+)ende_sau", line)
        if match:
            status = int(match.group(1))
            return status == 1
    return None


def parse_rgz_group_assignments(line: str) -> dict[int, list[int]]:
    """
    Parse group channel assignments from the 'rgz' command.

    Example response: 'start_rgz1,1,2,3,0,0,0,...ende_rgz'
    The controller sends one line per group with assigned channels.
    0 values mean no channel assigned.

    Returns dict with group number as key and list of channel numbers as value.
    """
    groups = {}
    if START_RGZ in line and END_RGZ in line:
        # Extract data between markers
        start_index = line.find(START_RGZ) + len(START_RGZ)
        end_index = line.rfind(END_RGZ)
        data_str = line[start_index:end_index]

        parts = data_str.split(",")
        if len(parts) > 0:
            try:
                group_num = int(parts[0])
                # Filter out 0 values (inactive channels)
                channels = [
                    int(ch)
                    for ch in parts[1:]
                    if ch.strip() and ch.strip() != "0" and int(ch) > 0
                ]
                if channels:  # Only add if group has channels
                    groups[group_num] = channels
                    _LOGGER.debug(
                        "Parsed group %d with channels %s", group_num, channels
                    )
            except (ValueError, IndexError) as e:
                _LOGGER.warning("Failed to parse group data: %s, error: %s", line, e)
    return groups


# Keep old function for backward compatibility but deprecate it
def parse_sgr_groups_output(line: str) -> dict[int, list[int]]:
    """
    Use parse_rgz_group_assignments instead (deprecated).

    DEPRECATED: SGR is a send command, not receive.
    The correct receive command is RGZ.
    """
    return parse_rgz_group_assignments(
        line.replace("start_sgr", "start_rgz").replace("ende_sgr", "ende_rgz")
    )


def parse_sgz_group_control_output(line: str) -> dict[int, dict[str, Any]]:
    """
    Parse group control settings from the 'sgz' command.

    Real data shows: 'start_sgz1,255,63,0,0,319,ende_sgz'

    The numbers appear to be bitmasks for channel assignments:
    - 255 (0xFF) = channels 1-8
    - 63 (0x3F) = channels 9-14
    etc.

    Returns dict with group number and extracted channel list + name.
    """
    group_info = {}
    if "start_sgz" in line and "ende_sgz" in line:
        try:
            start_index = line.find("start_sgz") + len("start_sgz")
            end_index = line.rfind("ende_sgz")
            data_str = line[start_index:end_index]

            parts = data_str.split(",")
            if len(parts) >= 2:
                group_num = int(parts[0])

                # Parse bitmasks to extract channel numbers
                channels = []
                for i, bitmask_str in enumerate(parts[1:]):
                    if not bitmask_str.strip():
                        continue
                    try:
                        bitmask = int(bitmask_str)
                        if bitmask == 0:
                            continue
                        # Check each bit in the bitmask
                        for bit in range(8):
                            if bitmask & (1 << bit):
                                channel = i * 8 + bit + 1  # Channel numbers start at 1
                                channels.append(channel)
                    except ValueError:
                        continue

                if channels:
                    name = f"Group {group_num}"
                    group_info[group_num] = {
                        "name": name,
                        "channels": channels
                    }
                    _LOGGER.debug("Parsed SGZ group %d: name='%s', channels=%s",
                                 group_num, name, channels)
        except (ValueError, IndexError) as e:
            _LOGGER.warning("Failed to parse SGZ data: %s, error: %s", line, e)
    return group_info


def parse_sld_logbook_entry(line: str) -> dict[str, Any] | None:
    """
    Parse logbook entry from the 'sld' command.

    Example response: 'start_sld1;Living Room;2024-12-27;09:15:30;up;Manual,ende_sld'
    Returns dict with logbook entry details.
    """
    if START_SLD in line and END_SLD in line:
        # Extract data between markers
        start_index = line.find(START_SLD) + len(START_SLD)
        end_index = line.rfind(END_SLD)
        data_str = line[start_index:end_index]

        # Logbook format: Nr;Motor/Raum;Datum;Uhrzeit;Richtung;Ausgelöst
        parts = data_str.split(";")
        if len(parts) >= 6:
            try:
                return {
                    "entry_number": int(parts[0]),
                    "motor_room": parts[1].strip(),
                    "date": parts[2].strip(),
                    "time": parts[3].strip(),
                    "direction": parts[4].strip(),
                    "trigger": parts[5].strip() if len(parts) > 5 else "",
                }
            except (ValueError, IndexError):
                _LOGGER.warning("Failed to parse logbook entry: %s", line)
    return None


def parse_sla_logbook_count(line: str) -> int:
    """
    Parse number of logbook entries from the 'sla' command.

    Example response: 'start_sla150ende_sla'
    Returns number of entries.
    """
    if START_SLA in line and END_SLA in line:
        match = re.match(r"start_sla(\d+)ende_sla", line)
        if match:
            return int(match.group(1))
    return 0


def parse_sjp_jalousie_params(line: str) -> dict[str, Any] | None:
    """
    Parse jalousie parameters from the 'sjp' command.

    Example response: 'start_sjp1,50,30,1,ende_sjp'
    Channel, tilt open angle, tilt close angle, tilt enabled
    """
    if START_SJP in line and END_SJP in line:
        start_index = line.find(START_SJP) + len(START_SJP)
        end_index = line.rfind(END_SJP)
        data_str = line[start_index:end_index]

        parts = data_str.split(",")
        if len(parts) >= 4:
            try:
                return {
                    "channel": int(parts[0]),
                    "tilt_open_angle": int(parts[1]),
                    "tilt_close_angle": int(parts[2]),
                    "tilt_enabled": int(parts[3]) == 1,
                }
            except (ValueError, IndexError):
                _LOGGER.warning("Failed to parse jalousie params: %s", line)
    return None


def parse_sfs_fixed_schedule(line: str) -> dict[str, Any] | None:
    """
    Parse fixed schedule from the 'sfs' command.

    Example response: 'start_sfs1,08:00,down,20:00,up,1,ende_sfs'
    """
    if START_SFS in line and END_SFS in line:
        start_index = line.find(START_SFS) + len(START_SFS)
        end_index = line.rfind(END_SFS)
        data_str = line[start_index:end_index]

        parts = data_str.split(",")
        if len(parts) >= 6:
            try:
                return {
                    "channel": int(parts[0]),
                    "time1": parts[1].strip(),
                    "action1": parts[2].strip(),
                    "time2": parts[3].strip(),
                    "action2": parts[4].strip(),
                    "enabled": int(parts[5]) == 1,
                }
            except (ValueError, IndexError):
                _LOGGER.warning("Failed to parse fixed schedule: %s", line)
    return None


def parse_sbp_shading_params(line: str) -> dict[str, Any] | None:
    """
    Parse shading parameters from the 'sbp' command.

    Example response: 'start_sbp1,50,30,1,ende_sbp'
    Channel, brightness threshold, position, enabled
    """
    if START_SBP in line and END_SBP in line:
        start_index = line.find(START_SBP) + len(START_SBP)
        end_index = line.rfind(END_SBP)
        data_str = line[start_index:end_index]

        parts = data_str.split(",")
        if len(parts) >= 4:
            try:
                return {
                    "channel": int(parts[0]),
                    "brightness_threshold": int(parts[1]),
                    "position": int(parts[2]),
                    "enabled": int(parts[3]) == 1,
                }
            except (ValueError, IndexError):
                _LOGGER.warning("Failed to parse shading params: %s", line)
    return None


def parse_automation_params(
    line: str, start_marker: str, end_marker: str
) -> dict[str, Any] | None:
    """
    Parse automation parameters (dawn, dusk, wind, rain).

    Common format: 'start_XXX1,threshold,action,enabled,ende_XXX'
    """
    if start_marker in line and end_marker in line:
        start_index = line.find(start_marker) + len(start_marker)
        end_index = line.rfind(end_marker)
        data_str = line[start_index:end_index]

        parts = data_str.split(",")
        if len(parts) >= 4:
            try:
                threshold = (
                    int(parts[1]) if parts[1].isdigit() else parts[1].strip()
                )
                return {
                    "channel": int(parts[0]),
                    "threshold": threshold,
                    "action": parts[2].strip(),
                    "enabled": int(parts[3]) == 1,
                }
            except (ValueError, IndexError):
                _LOGGER.warning("Failed to parse automation params: %s", line)
    return None


def parse_sdm_dawn_params(line: str) -> dict[str, Any] | None:
    """Parse dawn automation parameters."""
    return parse_automation_params(line, START_SDM, END_SDM)


def parse_sda_dusk_params(line: str) -> dict[str, Any] | None:
    """Parse dusk automation parameters."""
    return parse_automation_params(line, START_SDA, END_SDA)


def parse_swp_wind_params(line: str) -> dict[str, Any] | None:
    """Parse wind automation parameters."""
    return parse_automation_params(line, START_SWP, END_SWP)


def parse_srp_rain_params(line: str) -> dict[str, Any] | None:
    """Parse rain automation parameters."""
    return parse_automation_params(line, START_SRP, END_SRP)

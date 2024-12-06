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

def parse_skd_climate_data(line: str) -> dict[str, str]:
    """Get Climate data from the 'skd' command."""
    # Example response: 'start_skd0,999,999,999,999,999,999,999,999,0,0,0,0,1,0,0,ende_skd'
    if START_SKD in line and END_SKD in line:
        # Extract positions between 'start_sdk' and 'ende_sdk'
        start_index = line.find(START_SKD) + len(START_SKD)
        end_index = line.rfind(END_SKD)
        data_str = line[start_index:end_index]

        data_list = data_str.split(",")
        climate_data = {}
        for idx, data in enumerate(data_list, start=1):
            if idx > MAX_CHANNELS:
                break  # Stop processing further channels

            data = data.strip()  # Remove any leading/trailing whitespace

            match idx:
                case 1:
                    climate_data["brightness"] = data
                case 2:
                    if data != "999":
                        climate_data["indoor_temperature"] = data
                case 3:
                    if data != "999":
                        climate_data["indoor_temperature_decimal_place"] = data
                case 4:
                    if data != "999":
                        climate_data["indoor_temperature_min"] = data
                case 5:
                    if data != "999":
                        climate_data["indoor_temperature_max"] = data
                case 6:
                    if data != "999":
                        climate_data["outdoor_temperature"] = data
                case 7:
                    if data != "999":
                        climate_data["outdoor_temperature_decimal_place"] = data
                case 8:
                    if data != "999":
                        climate_data["outdoor_temperature_min"] = data
                case 9:
                    if data != "999":
                        climate_data["outdoor_temperature_max"] = data
                case 10:
                    climate_data["current_wind_speed"] = data
                case 11:
                    climate_data["current_wind_speed_max"] = data
                case 12:
                    climate_data["alarm"] = data
                case 13:
                    climate_data["rain"] = data
                case 15:
                    climate_data["brightness_medium"] = data
                case 16:
                    climate_data["relative_humidity"] = data
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

def _parse_string_output(line: str, start_command:str, stop_command) -> str:
    """Parse the output of any string command command."""
    if start_command in line and stop_command in line:
        match = re.match(rf"{start_command}(.+?){stop_command}", line)
        if match:
            return str(match.group(1))
    return "Unknown"

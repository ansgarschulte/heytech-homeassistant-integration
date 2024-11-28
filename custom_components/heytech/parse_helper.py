import logging
import re
from typing import Dict, Any

_LOGGER = logging.getLogger(__name__)

# Define the maximum number of channels supported by your Heytech system
MAX_CHANNELS = 32

MAX_POSITION = 132
START_SOP = "start_sop"
END_SOP = "ende_sop"
START_SMN = "start_smn"
END_SMN = "ende_smn"
START_SMC = "start_smc"
END_SMC = "ende_smc"

def parse_shutter_positions(line: str) -> dict[int, int]:
    # Handle responses with and without 'start_sop'

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
            _LOGGER.warning(
                "Invalid position value '%s' for channel %d", pos, idx
            )
            positions[idx] = 0  # Default to 0% if invalid
    return positions


def parse_smn_output(line:str) -> dict[Any, dict[str, int]]:
    """Listen and parse the output of the 'smn' command."""
    shutters = {}

    if START_SMN in line and END_SMN in line:
        match = re.match(r"start_smn(\d+),(.+?),(\d+),ende_smn", line)
        if match:
            channel = int(match.group(1))
            name = match.group(2).strip()
            shutters[name] = {"channel": channel}
    return shutters

def parse_smc_output(line: str) -> int:
    """Parse the output of the 'smc' command."""
    if START_SMC in line and END_SMC in line:
        # Example response: 'start_smc32ende_smc'
        match = re.match(r"start_smc(\d+)ende_smc", line)
        if match:
            return int(match.group(1))
    return 0
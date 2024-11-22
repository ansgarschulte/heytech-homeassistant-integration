# Heytech

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

![Project Maintenance][maintenance-shield]
[![BuyMeCoffee][buymecoffeebadge]][buymecoffee]

[![Discord][discord-shield]][discord]
[![Community Forum][forum-shield]][forum]
# Heytech Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/)

This is a custom integration for [Home Assistant](https://www.home-assistant.io/) that allows you to control your Heytech shutters.

---

## Features
- Control Heytech shutters directly from Home Assistant.
- Add and manage shutters dynamically through the Home Assistant interface.
- Seamless integration with Home Assistant's `Cover` platform.

---

## Installation

### Step 1: Add the Repository
1. Ensure that [HACS](https://hacs.xyz/) is installed in your Home Assistant setup.
2. Go to **HACS** → **Integrations**.
3. Click the three dots in the top-right corner and select **Custom repositories**.
4. Add this repository URL:
5. Choose **Integration** as the category and click **Add**.

### Step 2: Install the Integration
1. After adding the custom repository, search for "Heytech Home Assistant Integration" in HACS.
2. Click **Install** to add the integration to your setup.

### Step 3: Restart Home Assistant
1. Restart Home Assistant to apply the changes.
- Navigate to **Settings** → **System** → **Restart**.

---

## Configuration

### Add the Integration
1. After restarting, go to **Settings** → **Devices & Services** → **Add Integration**.
2. Search for **Heytech** and select it.
3. Enter the following details:
- **Host/IP**: The IP address or hostname of your Heytech hub.
- **Port**: The port number (default: `1002`).
- **Pin (optional)**: Your Heytech device PIN, if applicable.

### Add and Manage Shutters
- Once the integration is set up, you can add shutters via the integration settings:
1. Navigate to **Settings** → **Devices & Services** → **Heytech Integration**.
2. Select **Options** to add or manage shutters:
- **Add Shutter**: Provide a name and channel numbers (comma-separated) for each shutter.
- **Remove Shutter**: Remove shutters no longer in use.

---

## Example Configuration in Home Assistant

No manual YAML configuration is required, but the integration adds entities automatically, such as:
- `cover.living_room_shutter`
- `cover.bedroom_shutter`

You can control these shutters via Home Assistant UI, automations, or scripts.

---

## Troubleshooting
If you encounter any issues:
1. Check the **Logs** in Home Assistant for error messages.
2. Ensure your Heytech hub is reachable from the network.
3. Open an issue on the [GitHub repository](https://github.com/ansgarschulte/heytech-homeassistant-integration/issues).

---

## Support and Feedback
If you find any bugs or have feature requests, please open an issue in the [GitHub Issues section](https://github.com/ansgarschulte/heytech-homeassistant-integration/issues).
## Contributions are welcome!

If you want to contribute to this please read the [Contribution guidelines](CONTRIBUTING.md)

***

[heytech]: https://github.com/ansgarschulte/heytech-homeassistant-integration
[buymecoffee]: https://www.buymeacoffee.com/ansgarschulte
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=for-the-badge
[commits-shield]: https://img.shields.io/github/commit-activity/y/ansgarschulte/heytech-homeassistant-integration.svg?style=for-the-badge
[commits]: https://github.com/ansgarschulte/heytech-homeassistant-integration/commits/main
[discord]: https://discord.gg/Qa5fW2R
[discord-shield]: https://img.shields.io/discord/330944238910963714.svg?style=for-the-badge
[exampleimg]: example.png
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg?style=for-the-badge
[forum]: https://community.home-assistant.io/
[license-shield]: https://img.shields.io/github/license/ansgarschulte/heytech-homeassistant-integration.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-Ansgar%20Schulte%20%40ansgarschulte-blue.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/ansgarschulte/heytech-homeassistant-integration.svg?style=for-the-badge
[releases]: https://github.com/ansgarschulte/heytech-homeassistant-integration/releases

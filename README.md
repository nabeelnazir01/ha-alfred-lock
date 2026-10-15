# Alfred Smart Lock - Home Assistant Integration

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![GitHub Release](https://img.shields.io/github/v/release/nabeelnazir01/ha-alfred-lock)](https://github.com/nabeelnazir01/ha-alfred-lock/releases)

A custom integration for [Home Assistant](https://www.home-assistant.io/) to control and monitor **Alfred Smart Locks** via their cloud API (WiFi / Gateway bridge).

---

## Features

- **Lock Entity**:
  - Lock & Unlock status reporting.
  - Remote Lock & Unlock control commands.
- **Sensors**:
  - Battery percentage (`%`).
  - Signal / Wi-Fi strength.
  - Last activity / unlock event details.
- **Binary Sensors**:
  - Online / connectivity status.
  - Tamper / alarm alerts (if supported by lock model).
- **Configuration Flow**:
  - Interactive setup directly from the Home Assistant UI (Email & Password login).

---

## Installation via HACS (Recommended)

1. Make sure [HACS](https://hacs.xyz/) is installed in your Home Assistant instance.
2. In Home Assistant, open **HACS** > **Integrations**.
3. Click the **three dots menu (⋮)** in the top right corner and select **Custom repositories**.
4. In the Repository field, enter:
   ```text
   https://github.com/nabeelnazir01/ha-alfred-lock
   ```
5. Select category: **Integration**.
6. Click **Add**.
7. Locate **Alfred Smart Lock** in the HACS list and click **Download**.
8. **Restart Home Assistant**.

---

## Manual Installation

1. Download the latest release from the [Releases](https://github.com/nabeelnazir01/ha-alfred-lock/releases) tab.
2. Copy the `alfred_home` directory into your Home Assistant `<config>/custom_components/` folder.
   Your folder structure should look like this:
   ```text
   config/
   └── custom_components/
       └── alfred_home/
           ├── __init__.py
           ├── alfred_api.py
           ├── manifest.json
           ...
   ```
3. Restart Home Assistant.

---

## Configuration

1. In Home Assistant, navigate to **Settings** > **Devices & Services**.
2. Click **Add Integration** (bottom right).
3. Search for **Alfred Smart Lock**.
4. Enter your Alfred app account credentials (email and password).
5. Your Alfred lock(s) and gateway(s) will automatically populate with all supported entities.

---

## Requirements

- Alfred Smart Lock with a connected Alfred Wi-Fi Bridge / Gateway (WB1/WB2).
- Valid Alfred account credentials.

---

## Disclaimer & AI / Reverse Engineering Disclosure

- This is a community-developed integration and is not officially affiliated with or endorsed by Alfred Inc.
- **Reverse Engineering**: The underlying API communication and protocol details were derived by reverse-engineering the official Alfred Android application using [REA](https://github.com/morluto/rea).
- **AI-Assisted Development**: Portions of this codebase, protocol analysis, and documentation were developed and generated with the assistance of AI coding assistants.


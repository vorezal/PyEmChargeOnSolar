# PyEmChargeOnSolar

## Overview
This project integrates solar/battery and Emporia systems to automate the charging of electric vehicles. It aims to optimize energy usage by leveraging solar power and managing grid consumption efficiently.
Thanks to [magico13/PyEmVue](https://github.com/magico13/PyEmVue) for the Emporia API integration and [itayke/solaredge-emporia-autocharge](https://github.com/itayke/solaredge-emporia-autocharge) for the idea and basis for the script.

## Features
- Automated EV charging based on solar production
- Real-time monitoring of energy consumption
- Customizable charging schedules
- Integration with SolarEdge, Tesla Powerwall (via pyPowerwall Proxy) and Emporia APIs

## Installation
1. Clone the repository:
  ```sh
  git clone https://github.com/vorezal/PyEmChargeOnSolar
  ```
2. Navigate to the project directory:
  ```sh
  cd PyEmChargeOnSolar
  ```
3. Install the required dependencies:
  ```sh
  pip install -r requirements.txt
  ```

## Configuration
Create a `.env` file in the root directory and add your API keys and configuration settings:
```env
SOLAREDGE_SITE=site_number
SOLAREDGE_KEY='site_key'
EMPORIA_USER='emporia_user_email'
EMPORIA_PASSWORD='emporia_password'
```
All available settings are listed and documented in `pyemcose_shared.py`

### Getting a SolarEdge API Key
To get a SolarEdge API key, follow these steps:
1. Log in to your SolarEdge monitoring account.
2. Click the Admin link in the top menu.
3. Select the Site Access tab.
4. Activate API access.
5. Check the box to agree to the terms and conditions.
6. Click the New Key button.
7. Click Save.
8. Copy the API key and Site ID.

Note: This is a v1 API key which may change in the future.

### Setting up pyPowerwall Proxy
See [pypowerwall readme](https://github.com/jasonacox/pypowerwall/blob/main/proxy/README.md)

## Usage
Run in background with default values:
```sh
python pyemchargeonsolar.py &
```

Run as a docker container:
```docker
docker compose up -d
```

## License
This project is licensed under the GNU General Public License v3.0. See the [LICENSE](LICENSE) file for details.

## Contact
For any questions or support, please open an issue on the GitHub repository

from abc import ABC, abstractmethod
import requests
from dataclasses import dataclass
from datetime import datetime
from dateutil import parser
import pyemcos_shared
from pyemcos_shared import backoff

@dataclass
class PowerStats:
  solar_instant_watts: float
  load_instant_watts: float
  battery_instant_watts: float
  source_api: str

class DataProvider(ABC):
  @abstractmethod
  def fetch_data(self) -> dict:
    """Fetches data from a source and returns it in a standardized format."""
    pass

class SolarEdge(DataProvider):
  @backoff()
  def fetch_data(self) -> dict:
    print(f"Fetching power data from Solar Edge...")
    if not site_id:
      print(f"Site ID missing. Returning empty object.")
      return {
        "solar_instant_watts": 0,
        "load_instant_watts": 0,
        "battery_instant_watts": 0,
        "source": "Solar Edge",
      }

    api_endpoint = '/site/%s/powerDetails' % pyemcos_shared.SOLAREDGE_SITE_ID
    full_api_url = pyemcos_shared.SOLAREDGE_BASE_URL + api_endpoint

    parameters = {
      'api_key': pyemcos_shared.SOLAREDGE_KEY
    }

    try:
      response = requests.get(full_api_url)
    except:
      raise Exception("Error getting response from Solar Edge")

    if pyemcos_shared.verbose:
      print("Overview Response:", response)

    if pyemcos_shared.verbose:
      print(f"code {response.status_code} content {response.content}")
    if response.status_code != 200:
      raise Exception(response.status_code)

    data = response.json()
    prod_w = float(data.get('siteCurrentPowerFlow', {}).get('PV', {}).get('currentPower', 0))
    cons_w = float(data.get('siteCurrentPowerFlow', {}).get('LOAD', {}).get('currentPower', 0))
    bat_w = float(data.get('siteCurrentPowerFlow', {}).get('STORAGE', {}).get('currentPower', 0))

    return {
      "solar_instant_watts": prod_w,
      "load_instant_watts": cons_w,
      "battery_instant_watts": bat_w,
      "source": "Solar Edge",
    }

class PyPowerwallProxy(DataProvider):
  @backoff()
  def fetch_data(self) -> dict:
    print(f"Fetching power data from PyPowerwall-Proxy...")
    api_endpoint = '/aggregates'
    full_api_url = pyemcos_shared.PYPOWERWALL_PROXY_BASE_URL + api_endpoint
    response = requests.get(full_api_url)
    try:
      response = requests.get(full_api_url)
    except:
      raise Exception("Error getting response from pyPowerwall Proxy")

    if pyemcos_shared.verbose:
      print("Aggregates Response:", response)

    if pyemcos_shared.verbose:
      print(f"code {response.status_code} content {response.content}")
    if response.status_code != 200:
      raise Exception(response.status_code)

    data = response.json()
    prod_w = float(data.get('solar',{}).get('instant_power', 0))
    cons_w = float(data.get('load',{}).get('instant_power', 0))
    bat_w = float(data.get('battery',{}).get('instant_power', 0))
    return {
      "solar_instant_watts": prod_w,
      "load_instant_watts": cons_w,
      "battery_instant_watts": bat_w,
      "source": "pyPowerwall Proxy",
    }

class PowerData():
  provider = None

  def __init__(self, source_name: str):
    self.data_provider(source_name)

  def data_provider(self, source_name: str) -> DataProvider:
    if source_name == "solar_edge":
      self.provider = SolarEdge()
    elif source_name == "pypowerwall_proxy":
      self.provider = PyPowerwallProxy()
    else:
      raise ValueError(f"Unknown data source: {source_name}")

  def get(self) -> PowerStats:
    normalized_data = self.provider.fetch_data()

    if normalized_data is not None:
      return PowerStats(
        solar_instant_watts = normalized_data["solar_instant_watts"],
        load_instant_watts = normalized_data["load_instant_watts"],
        battery_instant_watts = normalized_data["battery_instant_watts"],
        source_api = normalized_data["source"],
      )

class SolarSchedule:
  sunrise = None
  sunset = None
  first_light = None
  last_light = None
  dawn = None
  dusk = None
  solar_noon = None
  golden_hour = None
  day_length = None
  timezone = None
  utc_offset = None
  lat = None
  lng = None

  def __init__(self, lat: str, lng: str):
    self.lat = lat
    self.lng = lng

  def update(self):
    if (None not in {self.lat, self.lng} and
        (None in {self.sunrise, self.sunset, self.first_light, self.last_light, self.dawn, self.dusk, self.solar_noon, self.golden_hour, self.day_length, self.timezone, self.utc_offset} or
        (self.sunrise is not None and self.sunrise.date() < datetime.today().date()))):
      try:
        response = requests.get("https://api.sunrisesunset.io/json?lat=" + self.lat + "&lng=" + self.lng)
      except:
        print("Error getting response from sunrisesunset.io")
        return
      if pyemcos_shared.verbose:
        print("Sunrise/Sunset Response:", response)

      if pyemcos_shared.verbose:
        print(f"code {response.status_code} content {response.content}")
      if response.status_code != 200:
        raise response.status_code
      data = response.json()
      date = data['results']['date']

      self.sunrise = parser.parse(date + " " + data['results']['sunrise'])
      self.sunset = parser.parse(date + " " + data['results']['sunset'])
      self.first_light = parser.parse(date + " " + data['results']['first_light'])
      self.last_light = parser.parse(date + " " + data['results']['last_light'])
      self.dawn = parser.parse(date + " " + data['results']['dawn'])
      self.dusk = parser.parse(date + " " + data['results']['dusk'])
      self.solar_noon = parser.parse(date + " " + data['results']['solar_noon'])
      self.golden_hour = parser.parse(date + " " + data['results']['golden_hour'])
      self.day_length = parser.parse(data['results']['day_length']).time()
      self.timezone = data['results']['timezone']
      self.utc_offset = data['results']['utc_offset']

  def get_sunrise(self):
    self.update()
    return self.sunrise

  def get_sunset(self):
    self.update()
    return self.sunset

  def get_first_light(self):
    self.update()
    return self.first_light

  def get_last_light(self):
    self.update()
    return self.last_light

  def get_dawn(self):
    self.update()
    return self.dawn

  def get_dusk(self):
    self.update()
    return self.dusk

  def get_solar_noon(self):
    self.update()
    return self.solar_noon

  def get_golden_hour(self):
    self.update()
    return self.golden_hour

  def get_day_length(self):
    self.update()
    return self.day_length

  def get_timezone(self):
    self.update()
    return self.timezone

  def get_utc_offset(self):
    self.update()
    return self.utc_offset

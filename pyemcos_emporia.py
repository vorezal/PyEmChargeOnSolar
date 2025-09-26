import os
import json
import pyemvue
from pyemvue.enums import Scale, Unit
import pyemcos_shared
from pyemcos_shared import backoff

class PyEmCoS_Emporia():
  # Create a new Emporia Vue object
  vue = pyemvue.PyEmVue()
  charger_device = None
  ev_charger = None

  def __init__(self):
    # Login to Emporia
    if os.path.exists(pyemcos_shared.EMPORIA_ACCESS_FILE):
      with open(pyemcos_shared.EMPORIA_ACCESS_FILE, 'r') as f:
        em_login_data = json.load(f)
    else:
      em_login_data = None

    # If no login data, use environment variables
    if not em_login_data:
      em_login_data = {
        'username': pyemcos_shared.EMPORIA_USER,
        'password': pyemcos_shared.EMPORIA_PASSWORD
      }
      with open(pyemcos_shared.EMPORIA_ACCESS_FILE, 'w') as f:
        json.dump(em_login_data, f)

    # Login to Emporia, either using the stored tokens or the username/password
    if em_login_data and 'id_token' in em_login_data and 'access_token' in em_login_data and 'refresh_token' in em_login_data:
      login_resp = self.vue.login(id_token=em_login_data['id_token'],
                   access_token=em_login_data['access_token'],
                   refresh_token=em_login_data['refresh_token'],
                   token_storage_file=pyemcos_shared.EMPORIA_ACCESS_FILE)
    else:
      login_resp = self.vue.login(username=em_login_data['username'],
                   password=em_login_data['password'],
                   token_storage_file=pyemcos_shared.EMPORIA_ACCESS_FILE)

    # Identify the charger
    self.get_charger()

    if self.charger_device is None:
      print("No charger device found!")

  @backoff()
  def get_device_list_usage(self):
    try:
      response = self.vue.get_device_list_usage(deviceGids=self.charger_device.device_gid, instant=None, scale=Scale.SECOND.value, unit=Unit.KWH.value)
    except:
      raise Exception("Error getting Emporia charger device usage")

    return response

  @backoff()
  def get_charger(self):
    try:
      devices = self.vue.get_devices()
      outlets, chargers = self.vue.get_devices_status()
    except:
      raise Exception("Error getting Emporia devices")

    for device in devices:
      if pyemcos_shared.verbose:
        print(device.device_gid, device.manufacturer_id, device.model, device.firmware)
      if device.ev_charger:
        if pyemcos_shared.verbose:
          print(f'EV Charger! On={device.ev_charger.charger_on} Charge rate: {device.ev_charger.charging_rate}A/{device.ev_charger.max_charging_rate}A')
        self.charger_device = device
        self.ev_charger = self.charger_device.ev_charger
        break

  def get_charger_state(self):
    self.get_charger()
    if self.ev_charger is not None:
      return {
        "charger_status": self.ev_charger.status,
        "charger_icon": self.ev_charger.icon,
        "charger_icon_label": self.ev_charger.icon_label,
        "charger_icon_detail_text": self.ev_charger.icon_detail_text,
        "charging_rate": self.ev_charger.charging_rate,
        "charger_on": self.ev_charger.charger_on,
        "charging_rate": self.ev_charger.charging_rate,
      }

  def set_charger_on(self, value):
    if not isinstance(value, bool):
      raise TypeError("charger_on must be a boolean.")
    self.ev_charger.charger_on = value

  def set_charging_rate(self, value):
    if not isinstance(value, int):
      raise TypeError("Charging rate must be an integer.")
    self.ev_charger.charging_rate = value

  @backoff()
  def update_charger(self):
    try:
      self.vue.update_charger(self.ev_charger)
    except:
      raise Exception("Error updating EV charger")

#!/usr/bin/python

# Emporia EV Solar Charging Maximizer
# Copyright (C) 2025 Itay Keren
# Copyright (C) 2025 Vorezal (Extended version)

# This script connects to Emporia's global APIs through the user's preset login credentials located at .env, 
# continuously maximizing EV charging throughput with available solar power, reducing electrical grid input as much as possible.
# Note that this script will stop charging if a minimum of 6 amps of solar power is not available for the previous WAIT_STOP cycles.

import os
import time
from datetime import datetime
from dateutil import parser
import sys
import numbers
import requests
import dns.resolver
import pyemcos_data
import pyemcos_emporia
import pyemcos_shared
#from pyemcos_shared import backoff

class PyEmChargeOnSolar:
  # Power objects
  emporia = None
  generation = None

  # Emporia stats
  script_charger_on = None
  charger_on = None
  charger_icon = None
  charger_icon_label = None
  charger_icon_detail_text = None
  charger_status = None
  charging_rate = None
  charger_usage_kw = None

  # Power stats
  prod_watts = None
  cons_watts = None
  bat_watts = None
  excess_kw = None

  # Calculated stats
  available_kw = []

  def __init__(self):
    self.emporia = pyemcos_emporia.PyEmCoS_Emporia()
    self.generation = pyemcos_data.PowerData(pyemcos_shared.POWER_API_SOURCE)

  def vue_calc_usage_recursive(self, usage_dict, depth=0) -> float:
    usage = 0
    for gid, device in usage_dict.items():
      for channelnum, channel in device.channels.items():
        if pyemcos_shared.verbose:
          print('-'*depth, f'{gid} {channelnum} {channel.name} {channel.usage*60} kwh')
        if isinstance(channel.usage*60, numbers.Number):
          usage += channel.usage*60
        if channel.nested_devices:
          usage += self.vue_calc_usage_recursive(channel.nested_devices, depth + 1)
    return usage

  def prune_available_kw(self):
    # Limit the list size
    if len(self.available_kw) > pyemcos_shared.historical_count:
        self.available_kw = self.available_kw[-pyemcos_shared.historical_count:]

  # Sliding average of a certain length
  def available_kw_sliding_average(self, count=0):
    if count > 0 and len(self.available_kw) >= count:
      # Calculate and return the average
      return sum(self.available_kw[-count:]) / min(count, len(self.available_kw))
    else:
      return 0

  # Sliding minimum of a certain length
  def available_kw_sliding_minimum(self, count=0):
    if count > 0 and len(self.available_kw) >= count:
      # Return the minimum
      return min(self.available_kw[-count:])
    else:
      return 0

  # Sliding maximum of a certain length
  def available_kw_sliding_maximum(self, count=0):
    if count > 0 and len(self.available_kw) >= count:
      # Return the maximum
      return max(self.available_kw[-count:])
    else:
      return 0

  def update_generation(self):
    # Get current power data
    power_data = self.generation.get()
    if pyemcos_shared.verbose:
      print("Data:", power_data)

    if power_data is None:
      self.prod_watts = 0
      self.cons_watts = 0
      self.bat_watts = 0
      self.excess_kw = 0
    else:
      self.prod_watts = power_data.solar_instant_watts
      self.cons_watts = power_data.load_instant_watts
      self.bat_watts = power_data.battery_instant_watts
      excess_w = self.prod_watts - self.cons_watts + min(self.bat_watts, 0)
      self.excess_kw = excess_w / 1000

  def update_emporia_usage(self):
    # Get current charger output to subtract from consumption
    device_usage_dict = self.emporia.get_device_list_usage()
    if device_usage_dict is not None:
      self.charger_usage_kw = round(self.vue_calc_usage_recursive(device_usage_dict) * 60.0, 2)
    else:
      self.charger_usage_kw = 0

  def update_emporia_status(self):
    charger_state = self.emporia.get_charger_state()

    if charger_state is None:
      self.charger_status = None
      self.charger_on = None
      self.charging_rate = None
      self.charger_icon = None
      self.charger_icon_label = None
      self.charger_icon_detail_text = None
    else:
      self.charger_status = charger_state['charger_status']
      self.charger_on = charger_state['charger_on']
      self.charging_rate = charger_state['charging_rate']
      self.charger_icon = charger_state['charger_icon']
      self.charger_icon_label = charger_state['charger_icon_label']
      self.charger_icon_detail_text = charger_state['charger_icon_detail_text']

  def update_power_available(self):
    if self.excess_kw is not None and self.charger_usage_kw is not None:
      available_for_charger_kw = round(self.excess_kw + self.charger_usage_kw, 2)
    else:
      available_for_charger_kw = 0

    self.available_kw.append(available_for_charger_kw)
    # Clean up historical data
    self.prune_available_kw()

  # Main service function: get site usage and current charge rate and update charge rate accordingly
  def update_charge_amp_by_power_data(self):
    # store original charging rate
    pre_change = self.charging_rate
    # calculate average power available and set final amps
    average_kw = round(self.available_kw_sliding_average(int(pyemcos_shared.SMOOTH)), 2)
    amps_from_kw = int(average_kw * 1000 / 240)
    amps = amps_from_kw + int(pyemcos_shared.OFFSET_AMPS)
    true_final_amps = max(min(amps, int(pyemcos_shared.MAX_AMPS)), 0)
    set_final_amps = max(min(amps, int(pyemcos_shared.MAX_AMPS)), int(pyemcos_shared.MIN_AMPS))

    # calculate power min and max, decide to enable or disable charger
    min_kw = round(self.available_kw_sliding_minimum(int(pyemcos_shared.WAIT_START)), 2)
    max_kw = round(self.available_kw_sliding_maximum(int(pyemcos_shared.WAIT_STOP)), 2)
    min_amps = int(min_kw * 1000 / 240) + int(pyemcos_shared.OFFSET_AMPS)
    max_amps = int(max_kw * 1000 / 240) + int(pyemcos_shared.OFFSET_AMPS)
    should_enable = min_amps >= int(pyemcos_shared.MIN_AMPS)
    should_disable = max_amps < int(pyemcos_shared.MIN_AMPS)

    if pyemcos_shared.verbose:
      print("Production Total Watts:", self.prod_watts)
      print("Consumption Total Watts:", self.cons_watts)
      print("Battery Total Watts:", self.bat_watts)
      print("Excess kW:", self.excess_kw)
      print("Charger Consumption kW:", self.charger_usage_kw)
      print("Available for Charger kW:", self.available_kw)
      print("Smoothed Value kW:", average_kw, "Smooth size", pyemcos_shared.SMOOTH)
      print("Should Enable:", should_enable)
      print("Should Disable:", should_disable)
      print("Final Amps:", set_final_amps)

    offset_str = f'+{pyemcos_shared.OFFSET_AMPS}={amps}' if int(pyemcos_shared.OFFSET_AMPS) > 0 else f'{pyemcos_shared.OFFSET_AMPS}={amps}' if int(pyemcos_shared.OFFSET_AMPS) < 0 else ''
    if pyemcos_shared.verbose:
      print(f'Desired Amp {amps_from_kw}{offset_str} Range {pyemcos_shared.MIN_AMPS}..{pyemcos_shared.MAX_AMPS}')

    if pyemcos_shared.verbose:
      print("Charger status:", self.charger_status)
      print("Script charger state:", self.script_charger_on)
      print("Actual charger state:", self.charger_on)
      print("Actual charger icon:", self.charger_icon)

    # continue only if and when charger status matches what was previously set by the script
    if self.script_charger_on is None or self.script_charger_on == self.charger_on:
      # if charger is off and true_final_amps is less than min_amps, do nothing
      if not self.charger_on and (not should_enable or true_final_amps < int(pyemcos_shared.MIN_AMPS)):
        self.script_charger_on = False
        print("Leaving charging disabled. Not enough power to meet minimum amps.")
      # if charger is off and true_final_amps is greater than or equal to min_amps, check if min power available has been greater than 1440 for WAIT_START cycles, turn on if true otherwise do nothing
      elif not self.charger_on and should_enable and true_final_amps >= int(pyemcos_shared.MIN_AMPS):
        self.script_charger_on = True
        self.emporia.set_charger_on(True)
        self.emporia.set_charging_rate(set_final_amps)
        self.emporia.update_charger()
        print("Enabling charging and setting Amps to", set_final_amps)
      # if charger is on and true_final_amps is less than min_amps, check if min power available is lower than 1440 for WAIT_STOP cycles, turn off if true otherwise do nothing
      elif self.charger_on and should_disable:
        self.script_charger_on = False
        self.emporia.set_charger_on(False)
        self.emporia.set_charging_rate(int(pyemcos_shared.MIN_AMPS))
        self.emporia.update_charger()
        print("Charging paused. Setting Amps to", set_final_amps)
      elif self.charger_on and pre_change == set_final_amps:
        self.script_charger_on = True
        print("No change -->", pre_change)
      elif self.charger_on:
        self.script_charger_on = True
        self.emporia.set_charging_rate(set_final_amps)
        self.emporia.update_charger()
        print("Amp changed", pre_change, "-->", set_final_amps)
      else:
        self.script_charger_on = False
        print("Charger is off and power is in an invalid state. Taking no action.")
    else:
      print("Charger state changed outside of script. Waiting until state matches again to resume.")

#
# Service
#

def main():
  start_time = None
  end_time = None
  schedule_on = None
  solarschedule = pyemcos_data.SolarSchedule(pyemcos_shared.LOCATION_LAT, pyemcos_shared.LOCATION_LNG)
  pyemchargeonsolar = PyEmChargeOnSolar()

  while True:
    now = datetime.now()
    dt_string = now.strftime("%Y-%m-%dT%H:%M:%S")
    print("=========", dt_string, "=========")

    # Skip if disabled by dns record or local file. Default to enabled.
    enabled = True
    if pyemcos_shared.DISABLE_DNS_TXT is not None:
      try:
        disabled_record = dns.resolver.resolve(pyemcos_shared.DISABLE_DNS_TXT,"TXT").response.answer[0][-1].strings[0]
      except:
        enabled = True
        print("DNS enabled true")

      if disabled_record != "False" and disabled_record != "0":
        enabled = False
        print("DNS enabled false")

    if pyemcos_shared.DISABLE_FILE is not None and os.path.exists(pyemcos_shared.DISABLE_FILE):
      enabled = False
      print("File disabled true")

    if enabled is True:
      if pyemcos_shared.SCHEDULE_START is not None and pyemcos_shared.SCHEDULE_END is not None:
        start_time = parser.parse(pyemcos_shared.SCHEDULE_START).time()
        end_time = parser.parse(pyemcos_shared.SCHEDULE_END).time()
        print("Using manual schedule:",start_time,end_time)
      elif pyemcos_shared.LOCATION_LAT is not None and pyemcos_shared.LOCATION_LNG is not None:
        start_time = solarschedule.get_sunrise().time()
        end_time = solarschedule.get_sunset().time()
        print("Using location schedule:",start_time,end_time)

      if start_time is None or end_time is None or start_time <= now.time() <= end_time:
        schedule_on = True
        # Update power generation stats
        pyemchargeonsolar.update_generation()
        # Update Emporia charger status
        pyemchargeonsolar.update_emporia_status()
        # Update Emporia charger usage stats if connected to vehicle and on, otherwise set to zero
        if pyemchargeonsolar.charger_icon == "CarConnected" and pyemchargeonsolar.charger_icon_label == "On":
          pyemchargeonsolar.update_emporia_usage()
        else:
          pyemchargeonsolar.charger_usage_kw = 0
        # Update available power stats
        pyemchargeonsolar.update_power_available()
        # Update charger state and output if connected to vehicle
        if pyemchargeonsolar.charger_icon == "CarConnected":
          pyemchargeonsolar.update_charge_amp_by_power_data()
        else:
          print("Charger is not connected to a vehicle. Skipping charger update.")
      elif schedule_on:
        # Outside of schedule, but schedule_on is True so it just ended this cycle. Make sure charger is off.
        if pyemchargeonsolar.charger_on:
          pyemchargeonsolar.emporia.set_charger_on(False)
          pyemchargeonsolar.emporia.set_charging_rate(int(pyemcos_shared.MIN_AMPS))
          pyemchargeonsolar.emporia.update_charger()

        schedule_on = False

    time.sleep(int(pyemcos_shared.FREQ))

if __name__ == '__main__':
  main()

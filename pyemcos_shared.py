import os
import time
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

POWER_API_SOURCE = os.getenv('POWER_API_SOURCE', 'pypowerwall_proxy')

# pyPowerwall Proxy base URL
PYPOWERWALL_PROXY_BASE_URL = os.getenv('PYPOWERWALL_PROXY_BASE_URL', 'http://localhost:8675')

# Retrieve SolarEdge credentials from environment variables
SOLAREDGE_SITE = os.getenv('SOLAREDGE_SITE')
SOLAREDGE_KEY = os.getenv('SOLAREDGE_KEY')
SOLAREDGE_BASE_URL = os.getenv('SOLAREDGE_BASE_URL', 'https://monitoringapi.solaredge.com')

# Emporia user and password
EMPORIA_USER = os.getenv('EMPORIA_USER')
EMPORIA_PASSWORD = os.getenv('EMPORIA_PASSWORD')

# Emporia Vue credentials
EMPORIA_ACCESS_FILE = '.credentials/emporia-access.json'

# Disable via DNS record
DISABLE_DNS_TXT = os.getenv('DISABLE_DNS_TXT')

# Disable via local file
DISABLE_FILE = os.getenv('DISABLE_FILE', 'volume/disable')

# Manual start and stop times. Overrides location based sunrise/sunset lookup. Specify datetime in ISO 8601 format e.g. %YYYY-%MM-%DDT%hh:%mm:%ss with no timezone (uses naive if unspecified)
SCHEDULE_START = os.getenv('SCHEDULE_START')
SCHEDULE_END = os.getenv('SCHEDULE_END')
# Location latitude and longitude for sunrise/sunset calculation
LOCATION_LAT = os.getenv('LOCATION_LAT')
LOCATION_LNG = os.getenv('LOCATION_LNG')

# Minimum charge rate. Emporia EVSEs can not be set below 6.
MIN_AMPS = os.getenv('MIN_AMPS', 6)
# Maximum charge rate. Emporia EVSEs can not be set above 48.
MAX_AMPS = os.getenv('MAX_AMPS', 48)
# Upate frequency in seconds, default 30.
FREQ = os.getenv('FREQ', 30)
# Smooth size, default 5. Min 1 (instant).
SMOOTH = os.getenv('SMOOTH', 5)
# Amp offset. Will set charge rate to this number of amps above or below actual solar available.
OFFSET_AMPS = os.getenv('OFFSET_AMPS', 0)

# Wait for excess power to exceed minimum for x loops before beginning/resuming charging
WAIT_START = os.getenv('WAIT_START', 6)
# Wait for excess power to fall below minimum for x loops before pausing charging
WAIT_STOP = os.getenv('WAIT_STOP', 3)

# Print extra info
VERBOSE = os.getenv('VERBOSE', 'false')

verbose_str = VERBOSE
verbose = ((verbose_str.isnumeric() and int(verbose_str) != 0) or verbose_str.lower() == "true")

# How many data points to keep for sliding calculations
historical_count = max(int(WAIT_START),int(WAIT_STOP))

# Shared backoff decorator
def backoff(delay=5, retries=3):
  def decorator(func):
    def wrapper(*args, **kwargs):
      current_retry = 0
      current_delay = delay
      while current_retry < retries:
        try:
          return func(*args, **kwargs)
        except Exception as e:
          current_retry += 1
          if current_retry >= retries:
            return
          print(f"Failed to execute function '{func.__name__}'. Retrying in {current_delay} seconds...")
          time.sleep(current_delay)
          current_delay *= 2
    return wrapper
  return decorator

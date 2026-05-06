import pytz
from datetime import datetime
import pandas as pd

# This script verifies that the US/Eastern timezone is correctly identified
# regardless of the local machine's timezone settings.

tz = pytz.timezone('US/Eastern')
now_et = datetime.now(tz)

print("--- Timezone Verification ---")
print(f"Current time in US/Eastern: {now_et}")
print(f"Current date in US/Eastern: {now_et.date()}")

# Test the logic used in UsTop100.py
target_date_str = None # Simulate "Today"
date_found = pd.to_datetime(target_date_str) if target_date_str else datetime.now(tz)
#print(f"Logic result (date_found):  {date_found.date()}")
print(f"Logic result (date_found):  {date_found}")
print("-----------------------------")

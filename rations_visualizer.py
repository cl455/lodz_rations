import streamlit
import string
from airtable import Airtable

# 1) Connect with Airtable.
AIRTABLE_API_KEY = "keygCUTG6e5DvySOR"
AIRTABLE_BASE_ID = "appXanlsMeENo7O1N"
AIRTABLE_TABLE_NAME = "Ration Announcements"
airtable = Airtable(api_key=AIRTABLE_API_KEY, base_key=AIRTABLE_BASE_ID, table_name=AIRTABLE_TABLE_NAME)
api_response = airtable.get_all()

# 2) Format the raw data from Airtable into a more workable form. Desired dictionary format:
# 
# {
# 	"1940-12-24": {
# 		"start_date": "1940-12-25",
# 		"duration": "5 days",
# 		"items": {
# 			"Zucker/Sugar (g)": 250,
# 			"Salz/Salt (g)": 150
# 		},
# 	},
# 	"1940-12-30": {
# 		"start_date": "1940-12-30",
# 		"duration": "1 day",
# 		"items": {
# 			"Zucker/Sugar (g)": 50,
# 		},
# 	},
# }
announcements = {}
for thing in api_response:
	data = thing["fields"]

	if "Begin Date" in data:
		start_date = data["Begin Date"]
	else:
		# Assume effective immediately
		start_date = data["Date"]

	if "Est. Duration" in data:
		# "Est. Duration" appears in the Airtable usually as "X days" or "X days (per coupon)"
		# Because it was always formatted this way, we can always rely on the number (of days) 
		# being the numerical value before the first whitespace
		duration_in_days = int(data["Est. Duration"].split(" ")[0])
	else:
		# Assume indefinite duration
		duration_in_days = None

	items = {}
	for key in data:
		if "(g)" in key:
			items[key] = data[key]

	announcements[data["Date"]] = {
		"start_date": start_date,
		"duration_in_days": duration_in_days,
		"items": items,
	}

# 3) At this point, we have a Python dictionary named 'announcements' that holds all of our data in a easily iterable format.
streamlit.write(announcements)

# 4) [TO-DO] Transform the 'announcements' dictionary into a different dictionary with the format:
# 
# {
# 	"Zucker/Sugar (g)": [50, 50, 50, ...],
# 	"Salz/Salt (g)": [30, 30, 30, 20, ...]
# }
# 
# Mapping each provision to list of length ~1200 (each index representating the nth day since
# the first ration announcement in the Chronicle) where the value at each index is the amount
# of mass of that provision that can be consumed that day. All lists should be the same length.

# Render a slider on the page.
# Example: streamlit.slider(label, min_value=None, max_value=None, value=None, step=None, format=None, key=None)
streamlit.slider("Amount of food", min_value=0, max_value=400, value=200, step=20)
streamlit.slider("Calories burned", min_value=0, max_value=400, value=200, step=20)
streamlit.slider("Household size", min_value=0, max_value=10, value=3, step=1)


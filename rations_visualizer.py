import altair
import pandas
import streamlit
import string
from airtable import Airtable
from collections import OrderedDict
from datetime import datetime, timedelta

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
ingredient_to_date_to_amounts = {}
for thing in api_response:
	data = thing["fields"]

	if "Begin Date" in data:
		start_date = data["Begin Date"]
	else:
		# Assume effective immediately
		start_date = data["Date"]

	if "Est. Duration" in data:
		# "Est. Duration" appears in the Airtable usually as "X days"/"X days (per coupon)"/"X week"
		# Because it was always formatted this way, we can always rely on the number (of days) 
		# being the numerical value before the first whitespace
		duration_in_days = int(data["Est. Duration"].split(" ")[0])
		if "week" in data["Est. Duration"]:
			duration_in_days *= 7
	else:
		# Assume 10 day duration otherwise
		duration_in_days = 10

	items = {}
	for key in data:
		if "(g)" in key:
			items[key] = data[key]
			ingredient_to_date_to_amounts[key] = {}

	announcements[data["Date"]] = {
		"start_date": start_date,
		"duration_in_days": duration_in_days,
		"items": items,
	}
announcements = OrderedDict(sorted(announcements.items()))

# 3) At this point, we have a Python dictionary named 'announcements' that holds all of our data in a easily iterable format.
# streamlit.dataframe(announcements)

# 4) Transform the 'announcements' dictionary into a different dictionary with the format:
# 
# {
# 	"Zucker/Sugar (g)": {
# 		"1940-12-25": 50,
# 		"1940-12-26": 50,
# 		...
# 	}
# }
# 
# Mapping each provision to list of length ~1200 (each index representating the nth day since
# the first ration announcement in the Chronicle) where the value at each index is the amount
# of mass of that provision that can be consumed that day. All lists should be the same length.
final_date = datetime.strptime(list(announcements.keys())[-1], "%Y-%m-%d")		# Get the date of the final announcement from the Chronicles

for announcement_date, announcement_info in announcements.items():
	for ingredient, ration_amount in announcement_info["items"].items():
		ration_effective_start_date = datetime.strptime(announcement_info["start_date"], "%Y-%m-%d")
		ration_effective_duration = announcement_info["duration_in_days"]
		for days_since_start in range(ration_effective_duration):
			current_date = ration_effective_start_date + timedelta(days_since_start)
			ingredient_to_date_to_amounts[ingredient][current_date.strftime("%Y-%m-%d")] = ration_amount / ration_effective_duration

# Order each ingredient's mapping of dates to amount available on that date by dates in ascending order.
for ingredient in ingredient_to_date_to_amounts.keys():
	ingredient_to_date_to_amounts[ingredient] = OrderedDict(sorted(ingredient_to_date_to_amounts[ingredient].items()))

for ingredient in ingredient_to_date_to_amounts.keys():
	streamlit.header(ingredient)
	dataframe = pandas.DataFrame({
		"date": ingredient_to_date_to_amounts[ingredient].keys(),
		"amount": ingredient_to_date_to_amounts[ingredient].values()

	})
	chart = altair.Chart(dataframe).mark_line().encode(
	    x=altair.X('date', axis=altair.Axis(labels=False)),
	    y=altair.Y('amount')
    )
	col1, col2 = streamlit.beta_columns([2, 1])
	col1.altair_chart(chart, use_container_width=True)
	col2.dataframe(dataframe)

# Render a slider on the page.
# Example: streamlit.slider(label, min_value=None, max_value=None, value=None, step=None, format=None, key=None)
streamlit.slider("Amount of food", min_value=0, max_value=400, value=200, step=20)
streamlit.slider("Calories burned", min_value=0, max_value=400, value=200, step=20)
streamlit.slider("Household size", min_value=0, max_value=10, value=3, step=1)


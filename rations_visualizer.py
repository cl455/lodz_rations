import altair
import pandas
import streamlit
import string
from airtable import Airtable
from collections import OrderedDict
from datetime import datetime, timedelta, date

def main():
	# 1) Connect with Airtable.
	data_from_airtable = get_data_from_airtable()

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
	announcements, ingredient_to_date_to_amounts = format_data_from_airtable(data_from_airtable)

	# 3) Transform the 'announcements' dictionary into a different dictionary with the format:
	# 
	# {
	# 	"Zucker/Sugar (g)": {
	# 		"1940-12-25": 50,
	# 		"1940-12-26": 50,
	# 		...
	# 	}
	# }
	# 
	# Mapping each provision to dictionary of dates to the amount available of that provision on that date.
	ingredient_to_date_to_amounts = calculate_available_rations_per_ingredient_per_day(announcements, ingredient_to_date_to_amounts)

	# 4) Visualize the amount available per day of each ingredient mentioned.
	visualize_amount_per_ingredient_available_over_time(ingredient_to_date_to_amounts)

	# 5) [TO-DO] Calculate the total amount of food (g) available each day over time.
	total_amount_by_date = calculate_total_amount_available_over_time(ingredient_to_date_to_amounts)

	# 6) [TO-DO] Visualize the total amount of food (g) available each day over time.
	visualize_total_amount_available_over_time(total_amount_by_date)

	# 7) Render some Streamlit sliders on the page (not connected to anything yet).
	render_sliders()

def get_data_from_airtable():
	AIRTABLE_API_KEY = "keygCUTG6e5DvySOR"
	AIRTABLE_BASE_ID = "appXanlsMeENo7O1N"
	AIRTABLE_TABLE_NAME = "Ration Announcements"
	airtable = Airtable(api_key=AIRTABLE_API_KEY, base_key=AIRTABLE_BASE_ID, table_name=AIRTABLE_TABLE_NAME)
	data_from_airtable = airtable.get_all()
	return data_from_airtable


def format_data_from_airtable(data_from_airtable):
	announcements = {}
	ingredient_to_date_to_amounts = {}
	for thing in data_from_airtable:
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
				all_announcement_dates = []
				first_announcement_date = date(1940, 3, 13)
				last_announcement_date = date(1944, 7, 18)     
				rations_duration = last_announcement_date - first_announcement_date
				for days_since_first_announcement in range(rations_duration.days):
					# .days cales the number of days integer value from rations_duration ... timedelta object
					day = first_announcement_date + timedelta(days_since_first_announcement)
					all_announcement_dates.append(day.strftime("%Y-%m-%d"))
				ingredient_to_date_to_amounts[key] = {date:0 for date in all_announcement_dates}

		announcements[data["Date"]] = {
			"start_date": start_date,
			"duration_in_days": duration_in_days,
			"items": items,
		}
	announcements = OrderedDict(sorted(announcements.items()))

	return announcements, ingredient_to_date_to_amounts


def calculate_available_rations_per_ingredient_per_day(announcements, ingredient_to_date_to_amounts):
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
	
	return ingredient_to_date_to_amounts


def visualize_amount_per_ingredient_available_over_time(ingredient_to_date_to_amounts):
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


def calculate_total_amount_available_over_time(ingredient_to_date_to_amounts):
	rations_per_day = {}
	for ingredient in ingredient_to_date_to_amounts.keys():
		for date in ingredient_to_date_to_amounts[ingredient].keys():
			if date in rations_per_day:
				rations_per_day[date] += ingredient_to_date_to_amounts[ingredient][date]
			else: 
				rations_per_day[date] = ingredient_to_date_to_amounts[ingredient][date]	
	return rations_per_day


def visualize_total_amount_available_over_time(rations_per_day):
	streamlit.header("daily_bread")
	dataframe = pandas.DataFrame({
		"date": rations_per_day.keys(),
		"amount": rations_per_day.values()

	})
	chart = altair.Chart(dataframe).mark_line().encode(
	    x=altair.X('date', axis=altair.Axis(labels=False)),
	    y=altair.Y('amount')
    )
	col1, col2 = streamlit.beta_columns([2, 1])
	col1.altair_chart(chart, use_container_width=True)
	col2.dataframe(dataframe)


def render_sliders():
	# Example: streamlit.slider(label, min_value=None, max_value=None, value=None, step=None, format=None, key=None)
	streamlit.slider("Amount of food", min_value=0, max_value=400, value=200, step=20)
	streamlit.slider("Calories burned", min_value=0, max_value=400, value=200, step=20)
	streamlit.slider("Household size", min_value=0, max_value=10, value=3, step=1)


if __name__ == "__main__":
    main()

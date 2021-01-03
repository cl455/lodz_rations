import altair
import pandas
import streamlit
import string
from airtable import Airtable
from collections import OrderedDict
from datetime import datetime, timedelta, date

def main():
	unit = render_unit_dropdown()

	# 1) Connect with Airtable.
	rations_data_from_airtable = get_rations_rations_data_from_airtable()
	caloric_values_from_airtable= get_caloric_values_from_airtable()

	# 2) Format the raw announements from Airtable into a more workable form. Desired dictionary format:
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
	announcements, item_to_date_to_amounts = format_rations_data_from_airtable(rations_data_from_airtable)

	# 3) Format the caloric data from Airtable into a more workable form. Desired dictionary format:
	# 
	# {
	# 	"Butter (g)": 150,
	# 	"Kohlrabi (g)": 37,
	# }
	item_to_calories = format_caloric_values_from_airtable(caloric_values_from_airtable)

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
	# Mapping each provision to dictionary of dates to the amount available of that provision on that date.
	item_to_date_to_amounts = calculate_available_rations_per_item_per_day(announcements, item_to_date_to_amounts)

	# 5) Perform a similar transformation with the caloric data, split out by day:
	# 
	# {
	# 	"Zucker/Sugar (g)": {
	# 		"1940-12-25": 20,
	# 		"1940-12-26": 20,
	# 		...
	# 	}
	# }
	item_to_date_to_calories = calculate_available_calories_per_item_per_day(item_to_date_to_amounts, item_to_calories)

	# 6) Visualize the amount available per day of each item mentioned.
	# visualize_amount_per_item_available_over_time(item_to_date_to_amounts)

	# 7) Calculate the total amount of food available each day over time, by both mass and calories.
	total_amount_by_date = calculate_total_amount_available_over_time(item_to_date_to_amounts)
	total_calories_by_date = calculate_total_calories_available_over_time(item_to_date_to_calories)


	# 8) Visualize the total amount of food available each day over time.
	if unit == "grams":
		visualize_total_amount_available_over_time(total_amount_by_date)
	else:
		visualize_total_calories_available_over_time(total_calories_by_date)


@streamlit.cache(persist=True, show_spinner=False)
def get_rations_rations_data_from_airtable():
	AIRTABLE_API_KEY = "keygCUTG6e5DvySOR"
	AIRTABLE_BASE_ID = "appXanlsMeENo7O1N"
	AIRTABLE_TABLE_NAME = "Ration Announcements"
	airtable = Airtable(api_key=AIRTABLE_API_KEY, base_key=AIRTABLE_BASE_ID, table_name=AIRTABLE_TABLE_NAME)
	rations_data_from_airtable = airtable.get_all()
	return rations_data_from_airtable


@streamlit.cache(persist=True, show_spinner=False)
def get_caloric_values_from_airtable():
	AIRTABLE_API_KEY = "keygCUTG6e5DvySOR"
	AIRTABLE_BASE_ID = "appXanlsMeENo7O1N"
	AIRTABLE_TABLE_NAME = "Caloric Value"
	airtable = Airtable(api_key=AIRTABLE_API_KEY, base_key=AIRTABLE_BASE_ID, table_name=AIRTABLE_TABLE_NAME)
	caloric_values_from_airtable = airtable.get_all()
	return caloric_values_from_airtable


@streamlit.cache(persist=True, allow_output_mutation=True, show_spinner=False)
def format_rations_data_from_airtable(rations_data_from_airtable):
	announcements = {}
	item_to_date_to_amounts = {}
	for thing in rations_data_from_airtable:
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
			if "(g)" in key or "(kg)" in key:
				all_announcement_dates = []
				first_announcement_date = date(1940, 3, 13)
				last_announcement_date = date(1944, 7, 18)  
				rations_duration = last_announcement_date - first_announcement_date
				
				for days_since_first_announcement in range(rations_duration.days):
					# .days cales the number of days integer value from rations_duration ... timedelta object
					day = first_announcement_date + timedelta(days_since_first_announcement)
					all_announcement_dates.append(day.strftime("%Y-%m-%d"))
				item_to_date_to_amounts[key] = {date:0 for date in all_announcement_dates}

				if "(g)" in key:
					items[key] = data[key]
				if "(kg)" in key:
					items[key] = data[key] * 1000

		announcements[data["Date"]] = {
			"start_date": start_date,
			"duration_in_days": duration_in_days,
			"items": items,
		}
	announcements = OrderedDict(sorted(announcements.items()))

	return announcements, item_to_date_to_amounts


@streamlit.cache(persist=True, allow_output_mutation=True, show_spinner=False)
def format_caloric_values_from_airtable(caloric_values_from_airtable):
	item_to_calories = {}
	for thing in caloric_values_from_airtable:
		data = thing["fields"]

		item = data["Label"]
		kcals_per_100g = data["Caloric Value (kcal/100g)"]
		item_to_calories[item] = kcals_per_100g
	return item_to_calories


@streamlit.cache(show_spinner=False)
def calculate_available_rations_per_item_per_day(announcements, item_to_date_to_amounts):
	for announcement_date, announcement_info in announcements.items():
		for item, ration_amount in announcement_info["items"].items():
			ration_effective_start_date = datetime.strptime(announcement_info["start_date"], "%Y-%m-%d")
			ration_effective_duration = announcement_info["duration_in_days"]
			for days_since_start in range(ration_effective_duration):
				current_date = ration_effective_start_date + timedelta(days_since_start)
				item_to_date_to_amounts[item][current_date.strftime("%Y-%m-%d")] = ration_amount / ration_effective_duration

	# Order each item's mapping of dates to amount available on that date by dates in ascending order.
	for item in item_to_date_to_amounts.keys():
		item_to_date_to_amounts[item] = OrderedDict(sorted(item_to_date_to_amounts[item].items()))
	
	return item_to_date_to_amounts


@streamlit.cache(show_spinner=False)
def calculate_available_calories_per_item_per_day(item_to_date_to_amounts, item_to_calories):
	item_to_date_to_calories = {}
	for item in item_to_date_to_amounts.keys():
		if item in item_to_calories.keys():
			item_to_date_to_calories[item] = {}
			for date in item_to_date_to_amounts[item].keys():
				item_to_date_to_calories[item][date] = item_to_date_to_amounts[item][date] * (item_to_calories[item] / 100.0)
	return item_to_date_to_calories


@streamlit.cache(show_spinner=False)
def visualize_amount_per_item_available_over_time(item_to_date_to_amounts):
	for item in item_to_date_to_amounts.keys():
		streamlit.header(item)
		dataframe = pandas.DataFrame({
			"date": item_to_date_to_amounts[item].keys(),
			"amount": item_to_date_to_amounts[item].values()

		})
		chart = altair.Chart(dataframe).mark_line().encode(
		    x=altair.X('date', axis=altair.Axis(labels=False)),
		    y=altair.Y('amount')
	    )
		col1, col2 = streamlit.beta_columns([2, 1])
		col1.altair_chart(chart, use_container_width=True)
		col2.dataframe(dataframe)


@streamlit.cache(show_spinner=False)
def calculate_total_amount_available_over_time(item_to_date_to_amounts):
	rations_per_day = {}
	for item in item_to_date_to_amounts.keys():
		for date in item_to_date_to_amounts[item].keys():
			if date in rations_per_day:
				rations_per_day[date] += item_to_date_to_amounts[item][date]
			else: 
				rations_per_day[date] = item_to_date_to_amounts[item][date]	
	return rations_per_day


@streamlit.cache(show_spinner=False)
def calculate_total_calories_available_over_time(item_to_date_to_calories):
	calories_per_day = {}
	for item in item_to_date_to_calories.keys():
		for date in item_to_date_to_calories[item].keys():
			if date in calories_per_day:
				calories_per_day[date] += item_to_date_to_calories[item][date]
			else: 
				calories_per_day[date] = item_to_date_to_calories[item][date]	
	return calories_per_day


def visualize_total_amount_available_over_time(rations_per_day):
	streamlit.header("Daily Bread")
	dataframe = pandas.DataFrame({
		"date": rations_per_day.keys(),
		"amount": rations_per_day.values()

	})
	chart = altair.Chart(dataframe).mark_line().encode(
	    x=altair.X('date', axis=altair.Axis(labels=False)),
	    y=altair.Y('amount')
    )
	streamlit.altair_chart(chart, use_container_width=True)
	with streamlit.beta_expander("View dataset"):
		streamlit.dataframe(dataframe)


def visualize_total_calories_available_over_time(calories_per_day):
	streamlit.header("Daily Bread")
	dataframe = pandas.DataFrame({
		"date": calories_per_day.keys(),
		"calories": calories_per_day.values()

	})
	chart = altair.Chart(dataframe).mark_line().encode(
	    x=altair.X('date', axis=altair.Axis(labels=False)),
	    y=altair.Y('calories')
    )
	streamlit.altair_chart(chart, use_container_width=True)
	with streamlit.beta_expander("View dataset"):
		streamlit.dataframe(dataframe)


def render_unit_dropdown():
	return streamlit.sidebar.selectbox("Visualize by", options=["grams", "calories"])


if __name__ == "__main__":
    main()

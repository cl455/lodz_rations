import altair
import pandas
import streamlit
import string
from airtable import Airtable
from collections import OrderedDict
from datetime import datetime, timedelta, date

def main():
	streamlit.set_page_config(page_title="Łódź Rations Visualizer")
	render_title()
	unit = render_unit_dropdown()

	# TODO: Utilize this setting
	strategy = render_rationing_strategy_dropdown()

	# 1) Connect with Airtable.
	rations_data_from_airtable = get_rations_rations_data_from_airtable()
	caloric_values_from_airtable= get_caloric_values_from_airtable()

	# 2) Format the raw announcements from Airtable into a more workable form. Desired dictionary format:
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
	announcements, item_to_date_to_amount = format_rations_data_from_airtable(rations_data_from_airtable)

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
	item_to_date_to_amount = calculate_available_rations_per_item_per_day(announcements, item_to_date_to_amount)

	# 5) Perform a similar transformation with the caloric data, split out by day:
	# 
	# {
	# 	"Zucker/Sugar (g)": {
	# 		"1940-12-25": 20,
	# 		"1940-12-26": 20,
	# 		...
	# 	}
	# }
	item_to_date_to_calories = calculate_available_calories_per_item_per_day(item_to_date_to_amount, item_to_calories)

	# 6) Visualize the amount available per day of each item mentioned.
	# visualize_amount_per_item_available_over_time(item_to_date_to_amount)

	# 7) Calculate the total amount of food available each day over time, by both mass and calories.
	total_amount_by_date = calculate_total_amount_available_over_time(item_to_date_to_amount)
	total_calories_by_date = calculate_total_calories_available_over_time(item_to_date_to_calories)

	# 8) Visualize the total amount of food available each day over time.
	if unit == "Mass (g)":
		streamlit.subheader(f"Given a {strategy.lower()} rationing strategy, this is the total amount of food that was available to a resident of the Łódź ghetto over time...")
		streamlit.text("")
		visualize_total_amount_available_over_time(total_amount_by_date)
		streamlit.text("")
		streamlit.text("")
		streamlit.text("")
		streamlit.subheader(f"and this is what was available...")
		streamlit.text("")
		visualize_amount_per_item_over_time(item_to_date_to_amount)
	else:
		streamlit.subheader(f"Given a {strategy.lower()} rationing strategy, this is the number of calories that were available to a resident of the Łódź ghetto over time...")
		streamlit.text("")
		visualize_total_calories_available_over_time(total_calories_by_date)
		streamlit.text("")
		streamlit.text("")
		streamlit.text("")
		streamlit.subheader(f"and this is what was available...")
		streamlit.text("")
		visualize_calories_per_item_over_time(item_to_date_to_calories)


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
	item_to_date_to_amount = {}
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
				item_to_date_to_amount[key] = {date:0 for date in all_announcement_dates}

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

	return announcements, item_to_date_to_amount


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
def calculate_available_rations_per_item_per_day(announcements, item_to_date_to_amount):
	for announcement_date, announcement_info in announcements.items():
		for item, ration_amount in announcement_info["items"].items():
			ration_effective_start_date = datetime.strptime(announcement_info["start_date"], "%Y-%m-%d")
			ration_effective_duration = announcement_info["duration_in_days"]
			for days_since_start in range(ration_effective_duration):
				current_date = ration_effective_start_date + timedelta(days_since_start)
				item_to_date_to_amount[item][current_date.strftime("%Y-%m-%d")] = ration_amount / ration_effective_duration

	# Order each item"s mapping of dates to amount available on that date by dates in ascending order.
	for item in item_to_date_to_amount.keys():
		item_to_date_to_amount[item] = OrderedDict(sorted(item_to_date_to_amount[item].items()))
	
	return item_to_date_to_amount


@streamlit.cache(show_spinner=False)
def calculate_available_calories_per_item_per_day(item_to_date_to_amount, item_to_calories):
	item_to_date_to_calories = {}
	for item in item_to_date_to_amount.keys():
		if item in item_to_calories.keys():
			item_to_date_to_calories[item] = {}
			for date in item_to_date_to_amount[item].keys():
				item_to_date_to_calories[item][date] = item_to_date_to_amount[item][date] * (item_to_calories[item] / 100.0)
	return item_to_date_to_calories


@streamlit.cache(show_spinner=False)
def visualize_amount_per_item_available_over_time(item_to_date_to_amount):
	for item in item_to_date_to_amount.keys():
		streamlit.header(item)
		dataframe = pandas.DataFrame({
			"Date": [datetime.strptime(date, "%Y-%m-%d") for date in item_to_date_to_amount[item].keys()],
			"Grams": item_to_date_to_amount[item].values()

		})
		chart = altair.Chart(dataframe).mark_line().encode(
		    x=altair.X("Date:T", scale=altair.Scale(zero=False), axis=altair.Axis(labelAngle=-45)),
		    y=altair.Y("Grams:Q"),
		    tooltip=["Date", "Grams"]
	    ).interactive()
		col1, col2 = streamlit.beta_columns([2, 1])
		col1.altair_chart(chart, use_container_width=True)
		col2.dataframe(dataframe)


@streamlit.cache(show_spinner=False)
def calculate_total_amount_available_over_time(item_to_date_to_amount):
	rations_per_day = {}
	for item in item_to_date_to_amount.keys():
		for date in item_to_date_to_amount[item].keys():
			if date in rations_per_day:
				rations_per_day[date] += item_to_date_to_amount[item][date]
			else: 
				rations_per_day[date] = item_to_date_to_amount[item][date]	
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
	dataframe = pandas.DataFrame({
		"Date": [datetime.strptime(date, "%Y-%m-%d") for date in rations_per_day.keys()],
		"Grams": rations_per_day.values()
	})
	chart = altair.Chart(dataframe).mark_line().encode(
	    x=altair.X("Date:T", scale=altair.Scale(zero=False), axis=altair.Axis(labelAngle=-45)),
	    y=altair.Y("Grams:Q"),
	    tooltip=["Date", "Grams"]
    ).interactive()
	streamlit.altair_chart(chart, use_container_width=True)
	# with streamlit.beta_expander("View dataset"):
	# 	streamlit.dataframe(dataframe)


def visualize_total_calories_available_over_time(calories_per_day):
	dataframe = pandas.DataFrame({
		"Date": [datetime.strptime(date, "%Y-%m-%d") for date in calories_per_day.keys()],
		"Calories": calories_per_day.values()
	})
	chart = altair.Chart(dataframe).mark_line().encode(
	    x=altair.X("Date:T", scale=altair.Scale(zero=False), axis=altair.Axis(labelAngle=-45)),
	    y=altair.Y("Calories:Q"),
	    tooltip=["Date", "Calories"]
    ).interactive()
	streamlit.altair_chart(chart, use_container_width=True)
	# with streamlit.beta_expander("View dataset"):
	# 	streamlit.dataframe(dataframe)


def visualize_amount_per_item_over_time(item_to_date_to_amount):
	dataframes = []
	for item in item_to_date_to_amount.keys():
		dataframe = pandas.DataFrame({
			"Item": item,
			"Date": [datetime.strptime(date, "%Y-%m-%d") for date in item_to_date_to_amount[item].keys()],
			"Amount": item_to_date_to_amount[item].values()
		})
		dataframes.append(dataframe)
	source = pandas.concat(dataframes)
	chart = altair.Chart(source).mark_area().encode(
	    altair.X("Date:T",
	        axis=altair.Axis(labelAngle=-45),
	    ),
	    altair.Y("sum(Amount):Q", stack="center", axis=None),
	    altair.Color("Item:N",
	        scale=altair.Scale(scheme="plasma")
	    )
	).interactive()
	streamlit.altair_chart(chart, use_container_width=True)
	# with streamlit.beta_expander("View dataset"):
	# 	streamlit.dataframe(source)


def visualize_calories_per_item_over_time(item_to_date_to_calories):
	dataframes = []
	for item in item_to_date_to_calories.keys():
		dataframe = pandas.DataFrame({
			"Item": item,
			"Date": [datetime.strptime(date, "%Y-%m-%d") for date in item_to_date_to_calories[item].keys()],
			"Calories": item_to_date_to_calories[item].values()
		})
		dataframes.append(dataframe)
	source = pandas.concat(dataframes)
	chart = altair.Chart(source).mark_area().encode(
	    altair.X("Date:T",
	        axis=altair.Axis(labelAngle=-45),
	    ),
	    altair.Y("sum(Calories):Q", stack="center", axis=None),
	    altair.Color("Item:N",
	        scale=altair.Scale(scheme="plasma")
	    )
	).interactive()
	streamlit.altair_chart(chart, use_container_width=True)
	# with streamlit.beta_expander("View dataset"):
	# 	streamlit.dataframe(source)


def render_title():
	streamlit.sidebar.title("Łódź Rations Visualizer")


def render_unit_dropdown():
	streamlit.sidebar.text("")
	streamlit.sidebar.text("")
	streamlit.sidebar.text("")
	streamlit.sidebar.text("")
	streamlit.sidebar.text("")
	streamlit.sidebar.text("")
	return streamlit.sidebar.selectbox("How would you like to measure your rations?", options=["Calories (kcal)", "Mass (g)"])


def render_rationing_strategy_dropdown():
	return streamlit.sidebar.radio("What's your rationing strategy?", options=["Clairvoyant", "Measured", "Reckless abandon"], index=1)


def render_date_slider(rations_per_day):
	first_announcement_date = datetime.strptime(list(rations_per_day.keys())[0], "%Y-%m-%d")
	last_announcement_date = datetime.strptime(list(rations_per_day.keys())[-1], "%Y-%m-%d")
	date_range = streamlit.slider(
		label="",
		min_value=first_announcement_date,
		max_value=last_announcement_date,
		value=(first_announcement_date, last_announcement_date)
	)
	return date_range


if __name__ == "__main__":
    main()

import altair
import numpy
import pandas
import streamlit
import string
from airtable import Airtable
from collections import OrderedDict
from datetime import datetime, timedelta, date


INEDIBLE_RATIONS = [
	"gespaltenem Holz/Split Wood",
	"Koksgrus (kg)",
	"Kohlen/Coal (kg)",
	"Kohlenstaub/Coal dust (kg)",
	"Streichhölzer/Matches (schachtel)",
	"Fliegenfänger (stück)",
	"Waschpulver (päcken)",
	"Waschsoda (g)",
	"Waschmittel \"Sil\" (300 g/pack)",
	"Seife/Soap (stück)",
]


########################
# Runs the Streamlit app
########################
def main():
	first_announcement_date = date(1940, 3, 13).strftime("%B %d, %Y")
	last_announcement_date = date(1944, 7, 18).strftime("%B %d, %Y")
	rations_duration = (date(1944, 7, 18) - date(1940, 3, 13)).days

	# 1) Render the sidebar
	streamlit.set_page_config(page_title="Łódź Rations Visualizer")
	render_title()
	unit = render_unit_dropdown()
	strategy = render_rationing_strategy_dropdown()

	lookahead_window = 7
	if "Clairvoyant" in strategy:
		lookahead_window = render_lookahead_dropdown()

	# 2) Connect with Airtable.
	rations_data_from_airtable = get_rations_data_from_airtable()
	caloric_values_from_airtable= get_caloric_values_from_airtable()

	# 3) Format the raw announcements from Airtable into a more workable form. Desired dictionary format:
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

	# 4) Format the caloric data from Airtable into a more workable form. Desired dictionary format:
	#
	# {
	# 	"Butter (g)": 150,
	# 	"Kohlrabi (g)": 37,
	# }
	item_to_calories, item_to_food_group = format_caloric_values_from_airtable(caloric_values_from_airtable)

	# 5) Transform the 'announcements' dictionary into a different dictionary with the format:
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
	item_to_date_to_announced_amount = calculate_announced_amount_per_item_per_day(announcements, item_to_date_to_amount)
	item_to_date_to_even_amount = calculate_available_rations_per_item_per_day(announcements, item_to_date_to_amount)

	# 6) Perform a similar transformation with the caloric data, split out by day:
	#
	# {
	# 	"Zucker/Sugar (g)": {
	# 		"1940-12-25": 20,
	# 		"1940-12-26": 20,
	# 		...
	# 	}
	# }
	item_to_date_to_announced_calories = calculate_available_calories_per_item_per_day(item_to_date_to_announced_amount, item_to_calories)
	item_to_date_to_even_calories = calculate_available_calories_per_item_per_day(item_to_date_to_even_amount, item_to_calories)

	# 7) Calculate the total of amount of food announced on each announcement date, both both mass and calories.
	announced_amount = calculate_total_amount_per_announcement(item_to_date_to_announced_amount)
	announced_calories = calculate_total_calories_per_announcement(item_to_date_to_announced_calories)

	# 8) Calculate the total amount of food available each day over time, by both mass and calories.
	even_amount = calculate_total_amount_available_over_time(item_to_date_to_even_amount)
	even_calories = calculate_total_calories_available_over_time(item_to_date_to_even_calories)

	# 9) If the user chose to visualize with a 'Clairvoyant' rationing strategy, calculate the total amount of food
	# available each day over time, by both mass and calories using a lookahead window of either 7/14/30 days.
	clairvoyant_amount = calculate_total_available_over_time_with_clairvoyance(even_amount, lookahead_window)
	clairvoyant_calories = calculate_total_available_over_time_with_clairvoyance(even_calories, lookahead_window)

	# 10) Visualize the total amount of food available each day over time.
	if unit == "Mass (g)":
		# Visualize main graph + 2 colorful graphs (in grams).
		if strategy == "None":
			streamlit.subheader(f"This is the total amount of food rations that was available to a resident of the Łódź ghetto over time...")
			streamlit.text("")
			visualize_total_amount_available_over_time(announced_amount)
			streamlit.text("")
			streamlit.text("")
			streamlit.text("")
			streamlit.subheader(f"These were the items available...")
			streamlit.text("")
			visualize_amount_per_item_over_time(item_to_date_to_announced_amount)
			streamlit.text("")
			streamlit.text("")
			streamlit.text("")
			streamlit.text("")
			streamlit.subheader(f"broken down by food group...")
			streamlit.text("")
			visualize_amount_per_food_group_over_time(item_to_date_to_announced_amount, item_to_food_group)
		else:	# Visualize in grams according to optionals strategy selection. Does not include the colorful graphs.
			streamlit.subheader(f"Given a {strategy.lower()} rationing strategy, this is the total amount of food rations that was available to a resident of the Łódź ghetto over time...")
			streamlit.text("")
			if "Even" in strategy:			
				visualize_total_amount_available_over_time(even_amount)
				days_without_food = calculate_number_of_days_without_food(even_amount)
			if "Clairvoyant" in strategy:
				visualize_total_amount_available_over_time(clairvoyant_amount)
				days_without_food = calculate_number_of_days_without_food(clairvoyant_amount)
			streamlit.text("")
			streamlit.subheader(f"This would have led to an estimated {days_without_food} days without food in the {rations_duration} days between {first_announcement_date} and {last_announcement_date}.")
	else:
		# Visualize main graph + 2 colorful graphs (in calories).
		if strategy == "None":
			streamlit.subheader(f"This is the caloric value of food rations that were available to a resident of the Łódź ghetto over time...")
			streamlit.text("")
			visualize_total_calories_available_over_time(announced_calories)
			streamlit.text("")
			streamlit.text("")
			streamlit.text("")
			streamlit.subheader(f"and this is what was available...")
			streamlit.text("")
			visualize_calories_per_item_over_time(item_to_date_to_announced_calories)
			streamlit.text("")
			streamlit.text("")
			streamlit.text("")
			streamlit.text("")
			streamlit.subheader(f"broken down by food group...")
			streamlit.text("")
			visualize_calories_per_food_group_over_time(item_to_date_to_announced_calories, item_to_food_group)
		else:	# Visualize in calories according to optionals strategy selection. Does not include the colorful graphs.
			streamlit.subheader(f"Given a {strategy.lower()} rationing strategy, this is the caloric value of food rations that were available to a resident of the Łódź ghetto over time...")
			streamlit.text("")
			if "Even" in strategy:
				visualize_total_calories_available_over_time(even_calories)
				days_without_food = calculate_number_of_days_without_food(even_calories)
			if "Clairvoyant" in strategy:
				visualize_total_calories_available_over_time(clairvoyant_amount)
				days_without_food = calculate_number_of_days_without_food(clairvoyant_amount)
			streamlit.text("")
			streamlit.subheader(f"This would have led to an estimated {days_without_food} days without food in the {rations_duration} days between {first_announcement_date} and {last_announcement_date}.")


#############################
# Airtable-related functions:
#############################
@streamlit.cache(suppress_st_warning=True, persist=True, show_spinner=False)
def get_rations_data_from_airtable():
	AIRTABLE_API_KEY = "keygCUTG6e5DvySOR"
	AIRTABLE_BASE_ID = "appXanlsMeENo7O1N"
	AIRTABLE_TABLE_NAME = "Ration Announcements"
	airtable = Airtable(api_key=AIRTABLE_API_KEY, base_key=AIRTABLE_BASE_ID, table_name=AIRTABLE_TABLE_NAME)
	rations_data_from_airtable = airtable.get_all()
	return rations_data_from_airtable


@streamlit.cache(suppress_st_warning=True, persist=True, show_spinner=False)
def get_caloric_values_from_airtable():
	AIRTABLE_API_KEY = "keygCUTG6e5DvySOR"
	AIRTABLE_BASE_ID = "appXanlsMeENo7O1N"
	AIRTABLE_TABLE_NAME = "Caloric Value"
	airtable = Airtable(api_key=AIRTABLE_API_KEY, base_key=AIRTABLE_BASE_ID, table_name=AIRTABLE_TABLE_NAME)
	caloric_values_from_airtable = airtable.get_all()
	return caloric_values_from_airtable

@streamlit.cache(suppress_st_warning=True, persist=True, show_spinner=False)
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
			# Filter out rations like coal, firewood, etc that can't be eaten.
			if key in INEDIBLE_RATIONS:
				continue
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


@streamlit.cache(suppress_st_warning=True, persist=True, show_spinner=False)
def format_caloric_values_from_airtable(caloric_values_from_airtable):
	item_to_calories = {}
	item_to_food_group = {}
	for thing in caloric_values_from_airtable:
		data = thing["fields"]

		item = data["Label"]
		kcals_per_100g = data["Caloric Value (kcal/100g)"]
		item_to_calories[item] = kcals_per_100g

		food_group = data["Food Group"]
		item_to_food_group[item] = food_group
	return item_to_calories, item_to_food_group





########################################################################
# Functions that do math to create dictionary datasets in helpful format
# (calculations, data transformations, augmentations):
########################################################################
@streamlit.cache(suppress_st_warning=True, persist=True, show_spinner=False)
def calculate_announced_amount_per_item_per_day(announcements, item_to_date_to_announced_amount):
	item_to_date_to_amount = dict(item_to_date_to_announced_amount)
	for announcement_date, announcement_info in announcements.items():
		for item, ration_amount in announcement_info["items"].items():
			item_to_date_to_amount[item][announcement_info["start_date"]] = ration_amount

	# Order each item"s mapping of dates to amount available on that date by dates in ascending order.
	for item in item_to_date_to_amount.keys():
		item_to_date_to_amount[item] = OrderedDict(sorted(item_to_date_to_amount[item].items()))

	return item_to_date_to_amount


@streamlit.cache(suppress_st_warning=True, persist=True, show_spinner=False)
def calculate_available_rations_per_item_per_day(announcements, item_to_date_to_amount):
	result = dict(item_to_date_to_amount)
	for announcement_date, announcement_info in announcements.items():
		for item, ration_amount in announcement_info["items"].items():
			ration_effective_start_date = datetime.strptime(announcement_info["start_date"], "%Y-%m-%d")
			ration_effective_duration = announcement_info["duration_in_days"]
			for days_since_start in range(ration_effective_duration):
				current_date = ration_effective_start_date + timedelta(days_since_start)
				result[item][current_date.strftime("%Y-%m-%d")] = ration_amount / ration_effective_duration

	# Order each item"s mapping of dates to amount available on that date by dates in ascending order.
	for item in result.keys():
		result[item] = OrderedDict(sorted(result[item].items()))

	return result

@streamlit.cache(suppress_st_warning=True, persist=True, show_spinner=False)
def calculate_available_calories_per_item_per_day(item_to_date_to_amount, item_to_calories):
	item_to_date_to_calories = {}
	for item in item_to_date_to_amount.keys():
		if item in item_to_calories.keys():
			item_to_date_to_calories[item] = {}
			for date in item_to_date_to_amount[item].keys():
				item_to_date_to_calories[item][date] = item_to_date_to_amount[item][date] * (item_to_calories[item] / 100.0)
	return item_to_date_to_calories


@streamlit.cache(suppress_st_warning=True, persist=True, show_spinner=False)
def calculate_total_amount_per_announcement(item_to_date_to_amount):
	rations_per_day = {}
	for item in item_to_date_to_amount.keys():
		for date in item_to_date_to_amount[item].keys():
			if date in rations_per_day:
				rations_per_day[date] += item_to_date_to_amount[item][date]
			else:
				rations_per_day[date] = item_to_date_to_amount[item][date]
	return rations_per_day


@streamlit.cache(suppress_st_warning=True, persist=True, show_spinner=False)
def calculate_total_calories_per_announcement(item_to_date_to_calories):
	calories_per_day = {}
	for item in item_to_date_to_calories.keys():
		for date in item_to_date_to_calories[item].keys():
			if date in calories_per_day:
				calories_per_day[date] += item_to_date_to_calories[item][date]
			else:
				calories_per_day[date] = item_to_date_to_calories[item][date]
	return calories_per_day


@streamlit.cache(suppress_st_warning=True, persist=True, show_spinner=False)
def calculate_total_amount_available_over_time(item_to_date_to_amount):
	rations_per_day = {}
	for item in item_to_date_to_amount.keys():
		for date in item_to_date_to_amount[item].keys():
			if date in rations_per_day:
				rations_per_day[date] += item_to_date_to_amount[item][date]
			else:
				rations_per_day[date] = item_to_date_to_amount[item][date]
	return rations_per_day


@streamlit.cache(suppress_st_warning=True, persist=True, show_spinner=False)
def calculate_total_calories_available_over_time(item_to_date_to_calories):
	calories_per_day = {}
	for item in item_to_date_to_calories.keys():
		for date in item_to_date_to_calories[item].keys():
			if date in calories_per_day:
				calories_per_day[date] += item_to_date_to_calories[item][date]
			else:
				calories_per_day[date] = item_to_date_to_calories[item][date]
	return calories_per_day


@streamlit.cache(suppress_st_warning=True, persist=True, show_spinner=False)
def calculate_total_available_over_time_with_clairvoyance(total_by_date, lookahead_window=7):
	total_by_date = _zero_fill_dates_without_food(total_by_date)
	dates_without_food = _get_dates_without_food(total_by_date)
	for date_without_food in dates_without_food:
		start_date = date_without_food - timedelta(days=lookahead_window)
		date_with_most_available = _get_date_with_most_available(total_by_date, start_date, date_without_food)
		while total_by_date[date_with_most_available.strftime("%Y-%m-%d")] > total_by_date[date_without_food.strftime("%Y-%m-%d")]:
			total_by_date[date_without_food.strftime("%Y-%m-%d")] += 1
			total_by_date[date_with_most_available.strftime("%Y-%m-%d")] -= 1
			date_with_most_available = _get_date_with_most_available(total_by_date, start_date, date_without_food)
	return total_by_date


def calculate_number_of_days_without_food(total_by_date):
	number_of_days_without_food = 0
	start_date = datetime.strptime(list(total_by_date.keys())[0], "%Y-%m-%d")
	end_date = datetime.strptime(list(total_by_date.keys())[-1], "%Y-%m-%d")
	num_days_in_dataset = (end_date - start_date).days
	for days_since_start in range(num_days_in_dataset):
		date = start_date + timedelta(days_since_start)
		date_string = date.strftime("%Y-%m-%d")
		if date_string not in total_by_date.keys() or total_by_date[date_string] == 0:
			number_of_days_without_food += 1
	return number_of_days_without_food


def _zero_fill_dates_without_food(total_by_date):
	start_date = datetime.strptime(list(total_by_date.keys())[0], "%Y-%m-%d")
	end_date = datetime.strptime(list(total_by_date.keys())[-1], "%Y-%m-%d")
	num_days_in_dataset = (end_date - start_date).days
	for days_since_start in range(num_days_in_dataset):
		date = start_date + timedelta(days_since_start)
		date_string = date.strftime("%Y-%m-%d")
		if date_string not in total_by_date.keys():
			total_by_date[date_string] = 0
	return total_by_date


def _get_dates_without_food(total_by_date):
	dates_without_food = []
	start_date = datetime.strptime(list(total_by_date.keys())[0], "%Y-%m-%d")
	end_date = datetime.strptime(list(total_by_date.keys())[-1], "%Y-%m-%d")
	num_days_in_dataset = (end_date - start_date).days
	for days_since_start in range(num_days_in_dataset):
		date = start_date + timedelta(days_since_start)
		date_string = date.strftime("%Y-%m-%d")
		if date_string not in total_by_date.keys() or total_by_date[date_string] == 0:
			dates_without_food.append(date)
	return dates_without_food


def _get_date_with_most_available(total_by_date, start_date, end_date):
	max_value = total_by_date[end_date.strftime("%Y-%m-%d")]
	max_date = end_date
	for days in range((end_date - start_date).days):
		date = start_date + timedelta(days=days)
		if date.strftime("%Y-%m-%d") not in total_by_date.keys():
			continue
		if total_by_date[date.strftime("%Y-%m-%d")] > max_value:
			max_value = total_by_date[date.strftime("%Y-%m-%d")]
			max_date = date
	return max_date





##################################################################################
# Functions that do the job of rendering graphs, toggles, dropdowns on the screen
##################################################################################
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


def visualize_announcements_by_item_in_grams(announcements):
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


def visualize_amount_per_food_group_over_time(item_to_date_to_amount, item_to_food_group):
	dataframes = []
	for item in item_to_date_to_amount.keys():
		# Try to get the item's food group.
		# If there isn't an entry to this item in the food group lookup, that probably means this item isn't edible.
		try:
			food_group = item_to_food_group[item]
		except KeyError:
			continue

		dataframe = pandas.DataFrame({
			"Food Group": food_group,
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
	    altair.Color("Food Group:N",
	        scale=altair.Scale(scheme="plasma")
	    )
	).interactive()
	streamlit.altair_chart(chart, use_container_width=True)


def visualize_calories_per_food_group_over_time(item_to_date_to_calories, item_to_food_group):
	dataframes = []
	for item in item_to_date_to_calories.keys():
		dataframe = pandas.DataFrame({
			"Food Group": item_to_food_group[item],
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
	    altair.Color("Food Group:N",
	        scale=altair.Scale(scheme="plasma")
	    )
	).interactive()
	streamlit.altair_chart(chart, use_container_width=True)


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
	return streamlit.sidebar.radio("What's your rationing strategy?", options=["None", "Clairvoyant (always with a morsel put aside)",
	 "Even (distribute daily allotment with faith in announcement information)"], index=0)


def render_lookahead_dropdown():
	return streamlit.sidebar.selectbox("How many days in the future do you want to be able to look ahead?", options=[7, 14, 30])


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




########################################################################################################
# This tells Python to run the app when we call 'streamlit run rations_visualizer.py' from the terminal.
########################################################################################################
if __name__ == "__main__":
    main()

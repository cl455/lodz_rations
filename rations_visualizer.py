import streamlit as st
from airtable import Airtable

AIRTABLE_API_KEY = "keygCUTG6e5DvySOR"

AIRTABLE_BASE_ID = "appXanlsMeENo7O1N"

AIRTABLE_TABLE_NAME = "Ration Announcements"

airtable = Airtable(api_key=AIRTABLE_API_KEY, base_key=AIRTABLE_BASE_ID, table_name=AIRTABLE_TABLE_NAME)

everything = airtable.get_all()

st.write(everything)

st.slider("Amount of food", min_value=0, max_value=400, value=200, step=20)
# streamlit.slider(label, min_value=None, max_value=None, value=None, step=None, format=None, key=None)


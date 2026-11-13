import math
import os
from urllib.parse import quote_plus
from pathlib import Path

import altair as alt
import pandas as pd
import pydeck as pdk
import requests
import streamlit as st

# listing_parser.py and suggestions.py sit next to this file; streamlit puts
# this folder on the path. streamlit re-runs this script on every change but
# keeps imported helper files in memory, so they are reloaded here to always
# use the latest version of them
import importlib

import exact_location
import listing_parser
import suggestions as suggestions_module

importlib.reload(exact_location)
importlib.reload(listing_parser)
importlib.reload(suggestions_module)
from exact_location import distances_km, geocode, parse_coordinates
from exact_location import nearest_places as nearest_from_point
from listing_parser import is_link, parse_listing
from suggestions import area_rates, build_suggestions, cheaper_nearby_areas

st.set_page_config(page_title="Bangalore Fair Price Checker", page_icon="🏠", layout="centered")

# paths are worked out from this file, so the app runs from any folder
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# the backend address can be changed without editing code: on a hosting
# platform it comes from the app's secrets or an environment variable,
# locally it falls back to the backend on this computer
def backend_address():
    try:
        if "FRONTEND_BACKEND_URL" in st.secrets:
            return st.secrets["FRONTEND_BACKEND_URL"]
    except Exception:
        pass  # no secrets file, which is normal when running locally
    return os.getenv("FRONTEND_BACKEND_URL", "http://127.0.0.1:8000")


BACKEND_URL = backend_address().rstrip("/")

# a free hosted backend sleeps when unused and takes up to a minute to wake,
# so requests wait longer than they would need to locally
REQUEST_TIMEOUT = 75

# a bit of custom styling - streamlit's config file only does flat colours,
# so the gradient and the card shadows have to be done with css
st.markdown("""
<style>
.stApp {
    background: linear-gradient(165deg, #375652 0%, #2C4643 45%, #243A38 100%);
}
[data-testid="stVerticalBlockBorderWrapper"] {
    background: #3A5B57;
    border-radius: 14px;
    border: 1px solid rgba(227, 181, 92, 0.28);
    box-shadow: 0 6px 18px rgba(0, 0, 0, 0.25);
}
[data-testid="stMetricValue"] {
    color: #E3B55C;
    font-weight: 600;
}
[data-testid="stMetricLabel"] {
    color: #C6D5D1;
}
h1, h2 {
    color: #F3EFE4;
}
h3 {
    color: #F3EFE4;
    border-left: 4px solid #E3B55C;
    padding-left: 12px;
}
</style>
""", unsafe_allow_html=True)


st.title("Bangalore Fair Price Checker")

st.write(
    "**Found a flat on a property website? Check whether its asking price is fair.** "
    "Paste the listing (or type its details), and our machine learning model gives an independent "
    "estimate of what the flat is worth today, explains why, and tells you what to check before buying."
)
st.caption(
    "We do not list flats for sale. Use property websites to find homes, contact owners and book visits, "
    "and use this tool to check the price."
)

# st.cache_data reads each file once, instead of on every click
@st.cache_data
def _read_csv(relative_path, modified_time):
    # modified_time is part of the cache key: when a file is updated (for
    # example new amenity names are fetched) the app reads the new version
    return pd.read_csv(PROJECT_ROOT / relative_path)


def load_csv(relative_path):
    """reads each file once and remembers it, until the file changes"""
    modified_time = (PROJECT_ROOT / relative_path).stat().st_mtime
    return _read_csv(relative_path, modified_time)


def load_report(relative_path):
    """reports are optional: if a script has not been run yet, skip that section"""
    try:
        return load_csv(relative_path)
    except FileNotFoundError:
        return None


data = load_csv("data/processed/bangalore_final_dataset.csv")

# the lookup holds only the 881 areas the model was trained on. the full
# dataset has 901, and the other 20 would get no price, so they are left out
location_info = load_csv("data/processed/location_lookup.csv").set_index("location")

location_list = sorted(location_info.index.tolist())

model_error = load_report("reports/model_error.csv")

# how much prices in each area have risen since our 2017-19 data, made by
# data_processing/build_price_adjustment.py. used to show today's price levels
market_table = load_report("data/processed/price_adjustment.csv")
MARKET_FACTORS = {}
CITY_FACTOR = 1.0
if market_table is not None:
    MARKET_FACTORS = market_table[market_table["location"] != "_city_"].set_index("location")["factor"].to_dict()
    city_rows = market_table.loc[market_table["location"] == "_city_", "factor"]
    CITY_FACTOR = float(city_rows.iloc[0]) if len(city_rows) else 1.0


def market_factor_for(area):
    """(factor, 'area' or 'city'): multiply 2017-19 prices by this for today's level"""
    if area in MARKET_FACTORS:
        return float(MARKET_FACTORS[area]), "area"
    return CITY_FACTOR, "city"

# the 5 nearest schools, hospitals and transit stops for each area, made by
# data_processing/fetch_amenity_names.py (one row per place). optional:
# without it the app shows distances only
amenity_places = load_report("data/processed/amenity_places.csv")
if amenity_places is not None:
    amenity_places = amenity_places[amenity_places["group"] != "none"]


def place_text(row):
    """'Delhi Public School (450 m)', with the kind of stop for transit"""
    text = str(row["name"]) + " (" + format_distance(row["km"]) + ")"
    if row["group"] == "transit" and isinstance(row["type"], str):
        text = text + " - " + row["type"]
    return text


def nearby_lists(area):
    """the up-to-5 nearest places in each group for an area, nearest first"""
    lists = {"school": [], "hospital": [], "transit": []}
    if amenity_places is None:
        return lists
    rows = amenity_places[amenity_places["location"] == area].sort_values(["group", "rank"])
    for _, row in rows.iterrows():
        if row["group"] in lists:
            lists[row["group"]].append(place_text(row))
    return lists


def nearest_places(area):
    """only the single nearest place in each group, or None if not known"""
    return {group: (texts[0] if texts else None) for group, texts in nearby_lists(area).items()}
    row = amenity_names.loc[area]
    for group in places:
        name = row.get(group + "_name")
        if isinstance(name, str) and name.strip():
            text = name.strip() + " (" + format_distance(row.get(group + "_km")) + ")"
            if group == "transit" and isinstance(row.get("transit_type"), str):
                text = row["transit_type"] + ": " + text
            places[group] = text
    return places
error_percent = float(model_error["mape_percent"].iloc[0]) if model_error is not None else 23.7


def format_distance(value):
    if value is None or pd.isna(value):
        return "not found"
    # a place right at the area centre would read "0 m"
    if float(value) < 0.05:
        return "under 50 m"
    # under 1 km reads better in metres: "13 m" instead of "0.0 km"
    if float(value) < 1:
        return str(int(round(float(value) * 1000))) + " m"
    return str(round(float(value), 1)) + " km"


def distance_km(lat1, lon1, lat2, lon2):
    R = 6371
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


if "predicted_price" not in st.session_state:
    st.session_state.predicted_price = None

if "verdict" not in st.session_state:
    st.session_state.verdict = None

if "price_factors" not in st.session_state:
    st.session_state.price_factors = []
    st.session_state.base_price = None

if "result" not in st.session_state:
    st.session_state.result = None

if "request" not in st.session_state:
    st.session_state.request = None


@st.cache_data(show_spinner=False)
def estimate_same_flat(location, size_sqft, bedrooms, bathrooms):
    """asks the API what the same flat would cost in another area.
    cached, so it is not asked again on every re-run"""
    try:
        response = requests.post(BACKEND_URL + "/predict", json={
            "location": location, "size_sqft": size_sqft,
            "bedrooms": bedrooms, "bathrooms": bathrooms,
        }, timeout=REQUEST_TIMEOUT)
        if response.status_code == 200:
            body = response.json()
            return body.get("today_price", body["predicted_price"])  # today's prices, like the main estimate
    except requests.exceptions.RequestException:
        pass
    return None

tab1, tab2, tab3, tab4 = st.tabs(["Check a Price", "Price Comparison", "Nearby Areas", "How It Works"])


# starting values for the inputs. they live in session_state (under the
# widgets' keys) so that "Fill in from this listing" can change them
input_defaults = {
    "input_location": "Whitefield" if "Whitefield" in location_list else location_list[0],
    "input_sqft": 1000, "input_bhk": 2, "input_bath": 2, "input_asking": 0,
}
for key, value in input_defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


def fill_from_listing():
    """runs when the button is clicked, before the inputs are drawn again,
    which is the moment Streamlit allows their values to be changed"""
    found = parse_listing(st.session_state.get("listing_text", ""), location_list)
    filled, missing = [], []

    if found["location"]:
        st.session_state.input_location = found["location"]
        filled.append(found["location"])
    else:
        missing.append("area (pick it from the list)")
    if found["bedrooms"]:
        st.session_state.input_bhk = max(1, found["bedrooms"])
        filled.append(str(found["bedrooms"]) + " BHK")
    else:
        missing.append("bedrooms")
    if found["size_sqft"]:
        st.session_state.input_sqft = max(100, int(found["size_sqft"]))
        filled.append(str(found["size_sqft"]) + " sqft")
    else:
        missing.append("size")
    if found["bathrooms"]:
        st.session_state.input_bath = max(1, found["bathrooms"])
        filled.append(str(found["bathrooms"]) + " bathrooms")
    else:
        missing.append("bathrooms")
    if found["asking_price"]:
        st.session_state.input_asking = int(round(found["asking_price"]))
        filled.append("asking price " + str(found["asking_price"]) + " Lakhs")
    else:
        missing.append("price")

    st.session_state.listing_message = (filled, missing)
    # remember the inputs as they were right after filling in. once the user
    # changes any of them, the "could not find" note has done its job and hides
    st.session_state.listing_snapshot = {key: st.session_state[key] for key in input_defaults}
    st.session_state.listing_was_link = is_link(st.session_state.get("listing_text", ""))


# every named school, hospital and transit stop in the city with its position,
# used to find what is nearest to an exact spot the user gives
city_places = load_report("data/processed/bangalore_places.csv")


@st.cache_data(show_spinner=False)
def cached_geocode(query):
    return geocode(query)


def find_exact_location():
    """runs when 'Find this place' is clicked: reads coordinates from a Google
    Maps link or typed numbers, otherwise looks the name up with Nominatim"""
    query = st.session_state.get("exact_query", "").strip()
    if not query:
        st.session_state.exact_message = ("warning", "Type a society, street or landmark, or paste a Google Maps link.")
        return

    point = parse_coordinates(query)
    label = None
    if point:
        label = "the coordinates you gave"
    else:
        found = cached_geocode(query)
        if found:
            # "Prestige Shantiniketan, Whitefield Road, Hoodi, ...India" -> the first 3 parts
            point, label = (found[0], found[1]), ", ".join(found[2].split(", ")[:3])
    if not point:
        st.session_state.exact_message = (
            "warning", "Could not find that place in Bangalore. Try the society name with the area, "
                       "e.g. \"Prestige Lakeside Habitat, Whitefield\", or paste a Google Maps link.")
        return

    area = st.session_state.input_location
    away = float(distances_km(point[0], point[1], [location_info.loc[area, "lat"]], [location_info.loc[area, "lon"]])[0])
    st.session_state.exact_point = {"lat": point[0], "lon": point[1], "label": label, "area": area}
    if away > 5:
        st.session_state.exact_message = (
            "warning", "Found " + label + ", but it is " + str(round(away, 1)) + " km from the centre of "
                       + area + ". Check that this is the right place, or pick the matching area above.")
    else:
        st.session_state.exact_message = (
            "success", "Found " + label + " (" + format_distance(away) + " from the centre of " + area
                       + "). The nearby places below are now measured from this exact spot.")


def clear_exact_location():
    st.session_state.pop("exact_point", None)
    st.session_state.pop("exact_message", None)
    st.session_state.exact_query = ""


def nearby_for(area):
    """the nearest places for an area: from the exact spot if the user gave one
    for this area, otherwise from the area's centre.
    returns (places by group, centre point dict, True if exact)"""
    exact = st.session_state.get("exact_point")
    if exact and exact["area"] == area and city_places is not None:
        centre = {"lat": exact["lat"], "lon": exact["lon"], "label": "This flat (the exact location you gave)"}
        return nearest_from_point(city_places, exact["lat"], exact["lon"]), centre, True

    places = {"school": [], "hospital": [], "transit": []}
    if amenity_places is not None:
        rows = amenity_places[amenity_places["location"] == area].sort_values(["group", "rank"])
        for _, row in rows.iterrows():
            if row["group"] in places:
                places[row["group"]].append({
                    "name": row["name"], "km": row["km"], "type": row["type"],
                    "lat": row.get("lat"), "lon": row.get("lon")})
    centre = {"lat": location_info.loc[area, "lat"], "lon": location_info.loc[area, "lon"],
              "label": "Centre of " + area + " (all listings here use this point)"}
    return places, centre, False


def place_line(group, place):
    text = str(place["name"]) + " (" + format_distance(place["km"]) + ")"
    if group == "transit" and isinstance(place.get("type"), str):
        text += " - " + place["type"]
    return text


def nearest_named(area):
    """only the single nearest place in each group, as text, or None"""
    places, _, _ = nearby_for(area)
    return {group: (place_line(group, items[0]) if items else None) for group, items in places.items()}


with tab1:
    st.header("Check a flat's price")

    # found a flat on a property website? paste its text and the inputs below
    # are filled in, so its asking price can be checked against our estimate
    with st.expander("📋 Step 1: paste the listing you found (or skip and type the details below)", expanded=True):
        st.text_area(
            "Listing text", key="listing_text", height=110,
            placeholder="e.g. 2 BHK Flat for sale in Whitefield, Bangalore. 1,150 sq.ft, 2 bathrooms. Price: Rs 85 Lac",
            help="Copy the title, price and details from any property website and paste them here",
        )
        st.button("Fill in from this listing", on_click=fill_from_listing)
        if "listing_message" in st.session_state:
            filled, missing = st.session_state.listing_message
            if filled:
                st.success("Filled in: " + ", ".join(filled) + ". Check the details below, then press Check Price.")
            snapshot = st.session_state.get("listing_snapshot", {})
            unchanged = all(st.session_state.get(key) == value for key, value in snapshot.items())
            if missing and unchanged:
                st.warning("The pasted text did not include: " + ", ".join(missing)
                           + ". Please fill these in below. (This note goes away once you do.)")
            if st.session_state.get("listing_was_link"):
                st.info("That is a web link. Property websites do not allow apps to open their pages, so we "
                        "can only read what is written in the link itself (usually the area and BHK).  \n"
                        "**To fill in everything:** open the link, select the title, price and details on the "
                        "page with your mouse, copy (Cmd+C), then paste that text here in place of the link "
                        "and click the button again.")

    selected_location = st.selectbox(
        "Location", location_list, key="input_location",
        help="Choose the neighborhood where the property is located"
    )
    size_sqft = st.number_input(
        "Size (sqft)", min_value=100, step=50, key="input_sqft",
        help="Total built-up area of the property, in square feet"
    )
    bedrooms = st.number_input(
        "Bedrooms (BHK)", min_value=1, step=1, key="input_bhk",
        help="Number of bedrooms in the property"
    )
    bathrooms = st.number_input(
        "Bathrooms", min_value=1, step=1, key="input_bath",
        help="Number of bathrooms in the property"
    )

    asking_price = st.number_input(
        "Asking price (Lakhs) - optional", min_value=0, step=1, key="input_asking",
        help="If you have a listing price, enter it to check if it looks fair"
    )

    dist_school = location_info.loc[selected_location, "dist_to_school_km"]
    dist_hospital = location_info.loc[selected_location, "dist_to_hospital_km"]
    dist_transit = location_info.loc[selected_location, "dist_to_transit_km"]

    # optional: the flat's exact spot, so nearby places are measured from it
    with st.expander("📍 Know the exact location? Get the places nearest to that spot (optional)"):
        st.text_input(
            "Society, street or landmark, or a Google Maps link / coordinates", key="exact_query",
            placeholder="e.g. Prestige Lakeside Habitat, Whitefield   or   https://maps.google.com/?q=12.9352,77.6974",
            help="Many listing pages show the society name or a map. In Google Maps, use Share to copy a link",
        )
        find_col, clear_col = st.columns([1, 1])
        find_col.button("Find this place", on_click=find_exact_location)
        clear_col.button("Use the area centre instead", on_click=clear_exact_location)
        if "exact_message" in st.session_state:
            kind, text = st.session_state.exact_message
            (st.success if kind == "success" else st.warning)(text)
        st.caption("This makes the nearby places exact. The price estimate still uses the area, because "
                   "the model was trained with every listing at its area's centre.")

    exact = st.session_state.get("exact_point")
    if exact and exact["area"] != selected_location:
        st.info("Your exact location was set for " + exact["area"] + ". Switch back to it, or use "
                "\"Use the area centre instead\" above.")

    nearby, map_centre, is_exact = nearby_for(selected_location)
    named = {group: (place_line(group, items[0]) if items else None) for group, items in nearby.items()}
    if any(named.values()):
        if is_exact:
            st.markdown("**What is nearby** (the 5 closest to the exact location you gave)")
        else:
            st.markdown("**What is nearby** (the 5 closest to the centre of " + selected_location + ")")
        near_col1, near_col2, near_col3 = st.columns(3)
        columns = [
            (near_col1, "🏫 Schools", "school", dist_school),
            (near_col2, "🏥 Hospitals and clinics", "hospital", dist_hospital),
            (near_col3, "🚌 Bus, Metro and train", "transit", dist_transit),
        ]
        for column, heading, group, model_distance in columns:
            column.markdown("**" + heading + "**")
            if nearby[group]:
                column.markdown("\n".join(str(i) + ". " + place_line(group, place)
                                          for i, place in enumerate(nearby[group], start=1)))
            else:
                column.caption("No named places found within 3 km.")
        if is_exact:
            st.caption("Places from OpenStreetMap within 3 km of the exact location you gave.")
        else:
            st.caption("Places from OpenStreetMap within 3 km, measured from the area's centre point, not the "
                       "exact house. Know the exact spot? Use the 📍 option above.")

        # the same places on a map, each with its real position from OpenStreetMap
        map_rows = pd.DataFrame([dict(place, group=group) for group, items in nearby.items() for place in items])
        if len(map_rows) > 0 and "lat" in map_rows.columns:
            map_rows = map_rows[map_rows["lat"].notna()].copy()
        if len(map_rows) > 0:
            colours = {"school": [70, 130, 255], "hospital": [235, 80, 80], "transit": [80, 200, 120]}
            labels = {"school": "School", "hospital": "Hospital / clinic", "transit": "Transit"}
            map_rows["colour"] = map_rows["group"].map(colours)
            map_rows["label"] = map_rows["group"].map(labels) + ": " + map_rows["name"].astype(str) \
                + " (" + map_rows["km"].apply(format_distance) + ")"
            centre = pd.DataFrame([{"lat": map_centre["lat"], "lon": map_centre["lon"],
                                    "colour": [227, 181, 92], "label": map_centre["label"]}])
            st.pydeck_chart(pdk.Deck(
                layers=[
                    pdk.Layer("ScatterplotLayer", data=map_rows, get_position="[lon, lat]",
                              get_fill_color="colour", get_radius=40, radius_min_pixels=5, pickable=True),
                    pdk.Layer("ScatterplotLayer", data=centre, get_position="[lon, lat]",
                              get_fill_color="colour", get_radius=70, radius_min_pixels=9, pickable=True),
                ],
                map_style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
                initial_view_state=pdk.ViewState(latitude=map_centre["lat"], longitude=map_centre["lon"], zoom=14),
                tooltip={"text": "{label}"},
            ))
            first_dot = "🟡 the flat" if is_exact else "🟡 area centre"
            st.caption(first_dot + "   🔵 schools   🔴 hospitals and clinics   🟢 bus, Metro and train. "
                       "Hover a dot to see its name.")
    else:
        st.write("Distance to nearest school:", format_distance(dist_school))
        st.write("Distance to nearest hospital:", format_distance(dist_hospital))
        st.write("Distance to nearest transit:", format_distance(dist_transit))

    # build a description using only real numbers from the dataset
    area_properties = data[data["location"] == selected_location]
    area_avg_per_sqft = (area_properties["price"] / area_properties["total_sqft_clean"]).median()  # median: a few luxury listings would pull the mean up

    sqft_per_bedroom = round(size_sqft / bedrooms)

    description = (
        "This is a " + str(bedrooms) + " BHK, " + str(bathrooms) + " bathroom property "
        + "covering " + str(size_sqft) + " sqft in " + selected_location + ", "
        + "which works out to about " + str(sqft_per_bedroom) + " sqft per bedroom. "
    )

    # when the named places are shown above, their distances are already on
    # screen, so they are not repeated here (and cannot disagree)
    if not any(named.values()):
        description += (
            "The nearest school is " + format_distance(dist_school) + " away, "
            + "the nearest hospital " + format_distance(dist_hospital) + ", and "
            + "the nearest transit stop " + format_distance(dist_transit) + ". "
        )

    area_factor, _ = market_factor_for(selected_location)
    if len(area_properties) > 0:
        description += (
            "There are " + str(len(area_properties)) + " listings in this area in our dataset. Brought up to "
            "today's market, flats here typically go for about "
            + format(int(round(area_avg_per_sqft * 100000 * area_factor, -2)), ",") + " rupees per sqft."
        )

    st.write(description)

    # what the listings in this area actually look like
    if len(area_properties) > 0:
        ready_count = (area_properties["availability"].astype(str).str.strip() == "Ready To Move").sum()
        ready_percent = round(ready_count / len(area_properties) * 100)

        common_type = area_properties["area_type"].mode()
        common_type_text = str(common_type.iloc[0]).strip() if len(common_type) > 0 else "unknown"

        cheapest = round(area_properties["price"].min(), 1)
        dearest = round(area_properties["price"].max(), 1)

        st.caption(
            "In our 2017-19 data for " + selected_location + ": " + str(ready_percent) + "% of listings were "
            + "ready to move, most were " + common_type_text + ", and prices ranged from "
            + str(cheapest) + " to " + str(dearest) + " Lakhs (before adjusting to today)."
        )

    # our data has no photos, so this finds real current listings for the area.
    # the user can paste one of them into the box at the top to check its price
    st.link_button(
        "🏠 See current " + str(bedrooms) + " BHK listings in " + selected_location + " (opens a web search)",
        "https://www.google.com/search?q=" + quote_plus(
            str(bedrooms) + " BHK flat for sale in " + selected_location + " Bangalore"),
    )
    st.caption("Found one you like? Copy its details into \"Paste its listing\" at the top to check "
               "whether its asking price is fair.")

    if st.button("Check Price", type="primary"):
        request_data = {
            "location": selected_location,
            "size_sqft": size_sqft,
            "bedrooms": bedrooms,
            "bathrooms": bathrooms
        }

        if asking_price > 0:
            request_data["asking_price"] = asking_price

        try:
            with st.spinner("Calculating predicted price... (the first one can take up to a minute "
                            "if the online server is waking up)"):
                response = requests.post(BACKEND_URL + "/predict", json=request_data, timeout=REQUEST_TIMEOUT)

            if response.status_code == 200:
                result = response.json()
                st.session_state.result = result
                # remember exactly what was priced, so the suggestions match it
                st.session_state.request = request_data
                st.session_state.predicted_price = result["predicted_price"]
                st.session_state.verdict = result.get("verdict")
                st.session_state.base_price = result.get("base_price")
                st.session_state.price_factors = result.get("factors", [])
            else:
                # 404 = unknown area, 422 = input outside the allowed range
                detail = response.json().get("detail", "")
                if isinstance(detail, list) and len(detail) > 0:
                    detail = detail[0].get("msg", "")
                st.error("The backend could not price this property: " + str(detail))
        except requests.exceptions.RequestException:
            st.error("Could not connect to the backend. Make sure the FastAPI server is running "
                     "(uvicorn backend.main:app --reload).")

    same_type_properties = data[(data["location"] == selected_location) & (data["bhk"] == bedrooms)]

    if st.session_state.predicted_price is not None:
        col1, col2 = st.columns(2)

        result = st.session_state.result or {}

        # the model learned from 2017-19 listings; the backend multiplies its
        # estimate by how much this area's prices have risen since
        model_price = st.session_state.predicted_price
        today_price = result.get("today_price", model_price)
        today_low = result.get("today_low", result.get("price_low", model_price))
        today_high = result.get("today_high", result.get("price_high", model_price))
        market_mult = result.get("market_factor", 1.0)
        basis = result.get("market_basis", "none")
        low, high = round(today_low), round(today_high)

        with col1:
            shown_error = result.get("error_percent", error_percent)
            st.metric("Estimated price today", str(low) + " - " + str(high) + " Lakhs")
            st.caption(
                "Best estimate: " + str(round(today_price, 1)) + " Lakhs, about "
                + format(int(result.get("today_price_per_sqft", result.get("price_per_sqft", 0))), ",")
                + " rupees per sqft. The range reflects our model's average error of about "
                + str(round(shown_error)) + "%."
            )

        with col2:
            if len(same_type_properties) > 0:
                typical_today = same_type_properties["price"].median() * market_mult
                difference = round(today_price - typical_today, 1)
                st.metric(
                    "Typical " + str(bedrooms) + " BHK here, today",
                    str(round(typical_today, 1)) + " Lakhs",
                    delta=str(difference) + " Lakhs (this flat vs typical)", delta_color="off",
                )
            else:
                st.write("No similar flats in our data for comparison")

        if basis != "none":
            where = ("prices in " + selected_location if basis == "area"
                     else "prices across Bangalore (no published rate for this area)")
            st.caption(
                "How we get today's price: our model estimates " + str(model_price) + " Lakhs at 2017-19 "
                "prices, then multiplies by **x" + str(round(market_mult, 2)) + "**, how much " + where
                + " have risen since, from published 2026 average rates. See How It Works for details."
            )

        for warning in result.get("warnings", []):
            st.warning(warning)

        if st.session_state.verdict is not None:
            difference = result.get("difference_percent")
            verdict_text = "Asking price check: " + st.session_state.verdict
            if difference is not None:
                verdict_text += (" (" + ("+" if difference > 0 else "") + str(difference)
                                 + "% vs our estimate of today's price)")
            if st.session_state.verdict == "Looks fairly priced":
                st.success(verdict_text)
            elif st.session_state.verdict == "Looks overpriced":
                st.error(verdict_text)
            else:
                st.info(verdict_text)

        # the "why this price" breakdown. the backend uses shap to split the
        # estimate into a starting price plus one push up or down per factor
        if st.session_state.base_price is not None and len(st.session_state.price_factors) > 0:
            with st.container(border=True):
                st.markdown("### Why this price?")
                st.write(
                    "We start from the average property in our data, "
                    + str(st.session_state.base_price) + " Lakhs, and each factor "
                    "below pushes the estimate up or down. Biggest effect first."
                )

                for factor in st.session_state.price_factors:
                    effect = factor["effect"]
                    if effect >= 0:
                        effect_text = ":green[+" + str(round(effect, 2)) + " Lakhs]"
                    else:
                        effect_text = ":red[" + str(round(effect, 2)) + " Lakhs]"
                    st.markdown(effect_text + "  -  " + factor["name"])

                st.caption(
                    "Starting price plus all the factors adds up to the model's estimate of "
                    + str(model_price) + " Lakhs at 2017-19 prices."
                    + (" Times x" + str(round(market_mult, 2)) + " market growth = about "
                       + str(round(today_price, 1)) + " Lakhs today." if basis != "none" else "")
                )

        # practical suggestions about this flat, worked out from real numbers
        priced = st.session_state.request
        if priced is not None and st.session_state.result is not None:
            nearby_estimates = []
            for area, km, rate in cheaper_nearby_areas(priced["location"], location_info, area_rates(data)):
                other = estimate_same_flat(area, priced["size_sqft"], priced["bedrooms"], priced["bathrooms"])
                if other is not None and other < today_price:
                    nearby_estimates.append((area, km, rate, other))

            # the suggestions compare asking prices (which are today's) with
            # today's estimate and today's area rates
            today_result = dict(st.session_state.result, predicted_price=today_price, price_low=today_low,
                                price_high=today_high,
                                price_per_sqft=result.get("today_price_per_sqft", result.get("price_per_sqft")))

            priced_nearby, _, priced_exact = nearby_for(priced["location"])
            exact_distances = None
            if priced_exact:
                exact_distances = {group: (items[0]["km"] if items else 99) for group, items in priced_nearby.items()}
            suggestions = build_suggestions(priced, today_result, data, location_info,
                                            nearby_estimates, nearest_named(priced["location"]), exact_distances,
                                            rate_factor=market_factor_for(priced["location"])[0])

            with st.container(border=True):
                st.markdown("### Suggestions for you")
                for kind, title, text in suggestions:
                    icon = {"good": "✅", "warning": "⚠️", "info": "💡"}[kind]
                    st.markdown(icon + " **" + title + "**  \n" + text)
                st.caption("Based on our data brought up to today's prices. These are pointers, not financial "
                           "or legal advice.")

        # what to verify before paying anything. no price model can check these
        with st.container(border=True):
            st.markdown("### Before you buy: check these yourself")
            st.markdown(
                "Our tool checks the **price**. It cannot check whether a listing, seller or flat is genuine. "
                "Before paying anything:\n"
                "1. **Visit the flat in person**, ideally twice at different times of day. Never pay for a flat "
                "you have only seen online.\n"
                "2. **Check the project's RERA registration** on the Karnataka RERA website (for new and "
                "under-construction projects). The RERA number should be on the listing.\n"
                "3. **Check the title and dues**: ask for the sale deed and an **encumbrance certificate (EC)**, "
                "which shows loans or claims on the property. ECs can be obtained from the Karnataka "
                "government's Kaveri online services or the sub-registrar's office.\n"
                "4. **Verify the seller**: their ID should match the owner named on the sale deed. For "
                "resale flats, also ask the housing society for a no-dues letter.\n"
                "5. **Never pay a token amount without a written agreement**, and pay by bank transfer, not cash.\n"
                "6. **Be careful with prices far below the market.** If our verdict says \"looks underpriced\", "
                "find out why before getting excited.\n"
                "7. **Get a lawyer to check the documents** before signing. For a home loan, the bank's own "
                "legal and valuation check adds another layer of safety."
            )
            st.caption("General guidance, not legal advice. Rules and procedures can change, so confirm "
                       "with the official websites or a property lawyer.")

        # a plain text summary the user can save or share
        summary_lines = [
            "Bangalore Fair Price Checker - price estimate",
            "Area: " + selected_location,
            "Property: " + str(bedrooms) + " BHK, " + str(bathrooms) + " bath, " + str(size_sqft) + " sqft",
            "Estimated price today: " + str(round(today_price, 1)) + " Lakhs (likely " + str(low) + " - "
            + str(high) + " Lakhs)",
            "Model estimate at 2017-19 prices: " + str(model_price) + " Lakhs, x" + str(round(market_mult, 2))
            + " market growth since",
        ]
        if st.session_state.verdict is not None:
            summary_lines.append("Asking price check: " + st.session_state.verdict)
        summary_lines.append("")
        summary_lines.append("Why this price (starting from " + str(st.session_state.base_price) + " Lakhs):")
        for factor in st.session_state.price_factors:
            summary_lines.append("  " + ("+" if factor["effect"] >= 0 else "") + str(factor["effect"])
                                 + " Lakhs  " + factor["name"])
        if priced is not None and st.session_state.result is not None:
            summary_lines.append("")
            summary_lines.append("Suggestions:")
            for kind, title, text in suggestions:
                summary_lines.append("- " + title + ": " + text)
        st.download_button(
            "Download this estimate",
            data="\n".join(summary_lines),
            file_name="price_estimate.txt",
        )

        # home loan EMI: the standard formula P x r x (1+r)^n / ((1+r)^n - 1)
        with st.expander("Home loan EMI calculator"):
            loan_col1, loan_col2, loan_col3 = st.columns(3)
            down_payment_percent = loan_col1.number_input("Down payment (%)", 0, 90, 20, step=5)
            interest_rate = loan_col2.number_input("Interest rate (% a year)", 1.0, 20.0, 8.5, step=0.1)
            years = loan_col3.number_input("Loan length (years)", 1, 30, 20, step=1)

            price_rupees = today_price * 100000
            loan_amount = price_rupees * (1 - down_payment_percent / 100)
            monthly_rate = interest_rate / 12 / 100
            months = years * 12

            if loan_amount > 0:
                growth = (1 + monthly_rate) ** months
                emi = loan_amount * monthly_rate * growth / (growth - 1)
                total_interest = emi * months - loan_amount
                st.metric("Monthly EMI", "Rs " + format(round(emi), ","))
                st.caption(
                    "Loan of Rs " + format(round(loan_amount), ",") + " over " + str(years)
                    + " years. Total interest paid: Rs " + format(round(total_interest), ",") + "."
                )
            else:
                st.caption("No loan needed with a 100% down payment.")

        st.info("See the Price Comparison tab for how this price compares with other flats in the area.")


selected_lat = location_info.loc[selected_location, "lat"]
selected_lon = location_info.loc[selected_location, "lon"]


with tab2:
    st.header("How does this price compare?")
    st.write(
        "Price per sqft of comparable flats in " + selected_location + ", brought up to today's market, "
        "with our estimate and the asking price marked."
    )
    st.caption(
        "These are historical records (around 2017-19) that our model was trained on, adjusted to today's "
        "price level. **They are not flats for sale**, and there is no owner or address to contact. To find "
        "flats that are for sale now, use a property website."
    )

    tab2_factor, tab2_basis = market_factor_for(selected_location)

    # comparables: same area and BHK if there are enough, otherwise widen
    comparables = data[(data["location"] == selected_location) & (data["bhk"] == bedrooms)]
    group_text = str(bedrooms) + " BHK flats in " + selected_location
    if len(comparables) < 5:
        comparables = data[data["location"] == selected_location]
        group_text = "flats of any size in " + selected_location + " (too few " + str(bedrooms) + " BHK records)"
    if len(comparables) < 5:
        comparables = data[data["bhk"] == bedrooms]
        group_text = str(bedrooms) + " BHK flats across Bangalore (too few records for " + selected_location + ")"
        tab2_factor, tab2_basis = CITY_FACTOR, "city"

    rates_today = (comparables["price"] / comparables["total_sqft_clean"] * 100000 * tab2_factor).round(-1)

    if len(rates_today) == 0:
        st.write("No comparable records found.")
    else:
        typical = rates_today.median()
        low_quarter, high_quarter = rates_today.quantile(0.25), rates_today.quantile(0.75)

        m1, m2, m3 = st.columns(3)
        m1.metric("Typical rate today (Rs/sqft)", format(int(round(typical, -2)), ","))
        m2.metric("Middle half (Rs/sqft)", format(int(round(low_quarter, -2)), ",") + " - "
                  + format(int(round(high_quarter, -2)), ","))
        m3.metric("Records compared", str(len(rates_today)))
        st.caption("Comparing " + group_text + ". Adjusted with x" + str(round(tab2_factor, 2))
                   + (" market growth for this area." if tab2_basis == "area" else " city-wide market growth."))

        # the rates to mark on the chart: our estimate, and the asking price if given
        markers = []
        priced = st.session_state.get("request")
        shown = st.session_state.get("result")
        same_flat = (priced is not None and shown is not None and priced["location"] == selected_location
                     and priced["bedrooms"] == bedrooms)
        if same_flat:
            estimate_rate = shown.get("today_price_per_sqft", shown.get("price_per_sqft"))
            markers.append({"rate": estimate_rate, "what": "Our estimate"})
            if priced.get("asking_price"):
                markers.append({"rate": priced["asking_price"] * 100000 / priced["size_sqft"], "what": "Asking price"})
        elif asking_price > 0:
            markers.append({"rate": asking_price * 100000 / size_sqft, "what": "Asking price"})

        chart_data = pd.DataFrame({"rate": rates_today})
        bars = alt.Chart(chart_data).mark_bar(color="#5E8C84").encode(
            x=alt.X("rate:Q", bin=alt.Bin(maxbins=30), title="Price per sqft at today's level (Rs)"),
            y=alt.Y("count():Q", title="Number of flats"),
            tooltip=[alt.Tooltip("count():Q", title="Flats")],
        )
        chart = bars
        if markers:
            marker_data = pd.DataFrame(markers)
            lines = alt.Chart(marker_data).mark_rule(strokeWidth=3).encode(
                x="rate:Q",
                color=alt.Color("what:N", title=None,
                                scale=alt.Scale(domain=["Our estimate", "Asking price"], range=["#E3B55C", "#EB5050"])),
                tooltip=[alt.Tooltip("what:N", title=""), alt.Tooltip("rate:Q", title="Rs per sqft", format=",.0f")],
            )
            chart = bars + lines
        st.altair_chart(chart.properties(height=320))

        # where the asking price sits among the comparables
        for marker in markers:
            share_cheaper = (rates_today < marker["rate"]).mean() * 100
            text = (marker["what"] + ": Rs " + format(int(round(marker["rate"], -1)), ",") + " per sqft, higher than "
                    + str(round(share_cheaper)) + "% of comparable flats.")
            if marker["what"] == "Asking price" and share_cheaper > 85:
                st.warning(text + " That is near the top of the range, so check what justifies it.")
            elif marker["what"] == "Asking price" and share_cheaper < 15:
                st.info(text + " That is near the bottom of the range, so check why it is so cheap.")
            else:
                st.write(text)
        if not markers:
            st.info("Check a price in the first tab (or enter an asking price) to see where it falls on this chart.")

    st.caption("Why per sqft? It lets flats of different sizes be compared fairly. "
               "Records are from the Kaggle Bengaluru House Price dataset; today's level uses published 2026 "
               "average asking rates (see How It Works).")


with tab3:
    st.header("Nearby Areas")
    st.write("The 10 areas closest to " + selected_location + ", with today's typical price per sqft. "
             "Useful if " + selected_location + " is over budget.")

    # only areas with enough records to trust their typical rate, and not
    # spelling variants of the chosen area itself (e.g. "Whitefield,")
    listing_counts = data["location"].value_counts()

    def simple_name(name):
        return "".join(ch for ch in str(name).lower() if ch.isalnum())

    nearby_list = []
    for loc_name, row in location_info.iterrows():
        if simple_name(loc_name) == simple_name(selected_location):
            continue
        if listing_counts.get(loc_name, 0) < 5:
            continue
        d = distance_km(selected_lat, selected_lon, row["lat"], row["lon"])
        nearby_list.append({"Neighborhood": loc_name, "distance_number": d})

    nearby_df = pd.DataFrame(nearby_list).sort_values("distance_number").head(10)
    nearby_df["Distance"] = nearby_df["distance_number"].apply(lambda x: str(round(x, 1)) + " km")

    # price per sqft in each area at today's level, so the user can see where
    # they get more space for their money
    area_rates = (data["price"] / data["total_sqft_clean"]).groupby(data["location"]).median() * 100000
    area_rates = pd.Series({area: rate * market_factor_for(area)[0] for area, rate in area_rates.items()})
    selected_rate = area_rates.get(selected_location)

    def rate_text(area):
        rate = area_rates.get(area)
        if pd.isna(rate):
            return "no data"
        return format(int(round(rate, -2)), ",") + " /sqft"

    def compare_text(area):
        rate = area_rates.get(area)
        if pd.isna(rate) or selected_rate is None or pd.isna(selected_rate):
            return "-"
        diff = (rate - selected_rate) / selected_rate * 100
        if diff > 5:
            return str(int(round(diff))) + "% pricier"
        if diff < -5:
            return str(int(round(abs(diff)))) + "% cheaper"
        return "about the same"

    nearby_df["Price per sqft"] = nearby_df["Neighborhood"].apply(rate_text)
    nearby_df["Compared to " + selected_location] = nearby_df["Neighborhood"].apply(compare_text)

    nearby_df = nearby_df[["Neighborhood", "Distance", "Price per sqft", "Compared to " + selected_location]]

    if selected_rate is not None and not pd.isna(selected_rate):
        st.write(
            selected_location + " is typically about "
            + format(int(round(selected_rate, -2)), ",") + " rupees per sqft today."
        )

    st.dataframe(nearby_df, hide_index=True, use_container_width=True)
    st.caption("Only areas with at least 5 records are listed. Median price per sqft from our 2017-19 data, multiplied by each area's market growth since "
               "(published 2026 rates, or the city-wide figure where an area has none).")


with tab4:
    st.header("What Drives the Price?")
    st.write(
        "We used SHAP to measure how much each factor affects the predicted price "
        "across all 11,272 properties in our dataset."
    )

    try:
        importance = pd.read_csv(PROJECT_ROOT / "reports" / "shap_feature_importance.csv")

        readable_names = {
            "total_sqft_clean": "Size (sqft)",
            "location_price": "Area price level",
            "bath": "Bathrooms",
            "bhk": "Bedrooms",
            "lat": "Latitude",
            "lon": "Longitude",
            "dist_to_hospital_km": "Distance to hospital",
            "dist_to_school_km": "Distance to school",
            "dist_to_transit_km": "Distance to transit",
        }
        importance["Factor"] = importance["feature"].map(readable_names).fillna(importance["feature"])
        importance["Average effect"] = importance["average_effect_lakhs"].apply(
            lambda x: str(round(x, 2)) + " Lakhs"
        )

        st.table(importance[["Factor", "Average effect"]])

        # work out the property vs location split from the numbers themselves
        property_columns = ["total_sqft_clean", "bhk", "bath"]
        is_property = importance["feature"].isin(property_columns)
        total_effect = importance["average_effect_lakhs"].sum()
        property_share = round(importance.loc[is_property, "average_effect_lakhs"].sum() / total_effect * 100)
        location_share = 100 - property_share

        st.write(
            "Property features (size, bedrooms, bathrooms) account for about "
            + str(property_share) + "% of the price effect. Location features account for about "
            + str(location_share) + "%. Within location, which area a property is in matters much "
            "more than how close it is to any single amenity."
        )
    except FileNotFoundError:
        st.write("Run the SHAP analysis script to see feature importance here.")

    summary_chart = PROJECT_ROOT / "reports" / "shap_summary.png"
    if summary_chart.exists():
        st.image(str(summary_chart), caption="Each dot is one property. Right = pushed the price up, "
                 "left = pushed it down. Red = high value of that feature, blue = low.")

    st.markdown("---")
    st.header("Does Location Help? The Experiment")
    st.write(
        "We trained the same models three times on the same 9,017 training properties "
        "and tested them on 2,255 properties they had never seen: with property details only, "
        "then adding map position and amenity distances, then adding the area's price level."
    )

    comparison = load_report("reports/model_comparison.csv")
    if comparison is not None:
        condition_names = {
            "area_rate_x_size": "Baseline: area rate x size",
            "property_only": "Property only",
            "plus_amenities": "+ position and amenities",
            "plus_area_price": "+ area price level (full)",
        }
        table = comparison.copy()
        table["Features used"] = table["condition"].map(condition_names).fillna(table["condition"])
        table = table.rename(columns={
            "model": "Model", "rmse": "RMSE (Lakhs)", "mae": "MAE (Lakhs)",
            "mape_percent": "MAPE (%)", "r2": "R2",
        })
        st.table(table[["Model", "Features used", "RMSE (Lakhs)", "MAE (Lakhs)", "MAPE (%)", "R2"]])
        st.caption("Lower RMSE, MAE and MAPE are better. R2 closer to 1 is better.")
    else:
        st.write("Run backend/models/train_random_forest_xgboost.py to see the comparison here.")

    if model_error is not None and "within_20_percent" in model_error.columns:
        error_row = model_error.iloc[0]
        e1, e2, e3 = st.columns(3)
        e1.metric("Average error", str(error_row["mape_percent"]) + "%")
        e2.metric("Within 10% of real price", str(error_row["within_10_percent"]) + "%")
        e3.metric("Within 20% of real price", str(error_row["within_20_percent"]) + "%")

    st.markdown("---")
    st.header("Bringing Prices Up to Today")
    st.write(
        "Our training data is from around 2017-19, and Bangalore prices have risen a lot since. The model "
        "learned the **pattern** (how size, rooms and area affect price) from that data. To get **today's** "
        "price, its estimate is multiplied by how much prices in that area have risen. This is called time "
        "adjustment, a standard method for valuation models whose data is older than today."
    )
    st.write(
        "For each area, we divide today's published average asking rate by the median rate in our data. "
        "Single-area figures are noisy, so each one is pulled toward the city-wide median, more strongly when "
        "an area has few records (shrinkage), and kept between x1.0 and x3.0. Areas without a published rate "
        "use the city-wide factor of **x" + str(round(CITY_FACTOR, 2)) + "**."
    )
    if market_table is not None:
        shown_areas = market_table[market_table["location"] != "_city_"].sort_values("listings", ascending=False).head(12)
        shown_areas = shown_areas.rename(columns={
            "location": "Area", "listings": "Records", "our_rate": "2017-19 rate (Rs/sqft)",
            "current_rate": "2026 rate (Rs/sqft)", "factor": "Factor used"})
        shown_areas = shown_areas[["Area", "Records", "2017-19 rate (Rs/sqft)", "2026 rate (Rs/sqft)", "Factor used"]].copy()
        for col in ["2017-19 rate (Rs/sqft)", "2026 rate (Rs/sqft)"]:
            shown_areas[col] = shown_areas[col].apply(lambda x: format(int(round(x)), ","))
        shown_areas["Factor used"] = shown_areas["Factor used"].apply(lambda x: "x" + format(x, ".2f"))
        st.dataframe(shown_areas, hide_index=True, use_container_width=True)
        st.caption(
            "2026 rates: Home Bazaar, \"Property Rates in Bangalore\", updated October 2026 (average asking rates). "
            "Asking prices on property sites tend to be higher than final registered sale prices, often by "
            "around a quarter, so treat today's estimates as asking-price levels."
        )

    st.markdown("---")
    st.header("About the Data")
    st.write(
        "We trained on the public Bengaluru House Price dataset from Kaggle: about 13,000 listings from "
        "around 2017-19. It is anonymized: there are no addresses, photos or real society names, and the "
        "listings cannot be verified or contacted. Possession dates in it, like '18-May', mean May 2018. "
        "No free, current, address-level price data exists for Bangalore, which is why prices are adjusted "
        "to today as described above."
    )

    st.markdown("---")
    st.header("How It Works")
    st.write(
        "This tool uses a machine learning model (XGBoost) trained on thousands of real "
        "property listings across Bangalore. It looks at the property's size, number of "
        "bedrooms and bathrooms, its location, and how close that location is to schools, "
        "hospitals, and public transit, to estimate a fair market price."
    )
    st.write(
        "The prediction is an estimate, not a guarantee. Real prices can vary based on "
        "things this tool doesn't capture, like the property's condition, floor, or exact address."
    )
    st.write(
        "Data source: Bengaluru House Price Data (Kaggle). Amenity distances come from "
        "OpenStreetMap."
    )

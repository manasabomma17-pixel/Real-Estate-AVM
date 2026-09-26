import streamlit as st
import pandas as pd
import pydeck as pdk
import requests
import math

st.title("Real Estate AVM - Price Predictor")

st.write(
    "Welcome! This tool estimates what a property in Bangalore might sell for, "
    "based on real sales data. Enter your property details in the first tab, "
    "then explore similar properties and nearby areas in the other tabs."
)

data = pd.read_csv("data/processed/bangalore_final_dataset.csv")

location_info = data.drop_duplicates(subset="location")[
    ["location", "lat", "lon", "dist_to_school_km", "dist_to_hospital_km", "dist_to_transit_km"]
]
location_info = location_info.set_index("location")

location_list = sorted(location_info.index.tolist())


def format_distance(value):
    if pd.isna(value):
        return "not found"
    return str(round(value, 1)) + " km"


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

tab1, tab2, tab3, tab4 = st.tabs(["Predict Price", "Similar Properties", "Nearby Neighborhoods", "How It Works"])


with tab1:
    st.header("Enter Property Details")

    selected_location = st.selectbox(
        "Location", location_list,
        help="Choose the neighborhood where the property is located"
    )
    size_sqft = st.number_input(
        "Size (sqft)", min_value=100, value=1000, step=50,
        help="Total built-up area of the property, in square feet"
    )
    bedrooms = st.number_input(
        "Bedrooms (BHK)", min_value=1, value=2, step=1,
        help="Number of bedrooms in the property"
    )
    bathrooms = st.number_input(
        "Bathrooms", min_value=1, value=2, step=1,
        help="Number of bathrooms in the property"
    )

    asking_price = st.number_input(
        "Asking price (Lakhs) - optional", min_value=0, value=0, step=1,
        help="If you have a listing price, enter it to check if it looks fair"
    )

    dist_school = location_info.loc[selected_location, "dist_to_school_km"]
    dist_hospital = location_info.loc[selected_location, "dist_to_hospital_km"]
    dist_transit = location_info.loc[selected_location, "dist_to_transit_km"]

    st.write("Distance to nearest school:", format_distance(dist_school))
    st.write("Distance to nearest hospital:", format_distance(dist_hospital))
    st.write("Distance to nearest transit:", format_distance(dist_transit))

    description = (
        "This is a " + str(bedrooms) + " BHK, " + str(bathrooms) + " bathroom property "
        + "covering " + str(size_sqft) + " sqft, located in " + selected_location + ". "
        + "It is about " + format_distance(dist_school) + " from the nearest school, "
        + format_distance(dist_hospital) + " from the nearest hospital, and "
        + format_distance(dist_transit) + " from the nearest transit stop."
    )
    st.write(description)

    if st.button("Predict Price"):
        request_data = {
            "location": selected_location,
            "size_sqft": size_sqft,
            "bedrooms": bedrooms,
            "bathrooms": bathrooms
        }

        if asking_price > 0:
            request_data["asking_price"] = asking_price

        try:
            with st.spinner("Calculating predicted price..."):
                response = requests.post("http://127.0.0.1:8000/predict", json=request_data)
                result = response.json()
                st.session_state.predicted_price = result["predicted_price"]
                st.session_state.verdict = result.get("verdict")
        except:
            st.error("Could not connect to the backend. Make sure the FastAPI server is running.")

    same_type_properties = data[(data["location"] == selected_location) & (data["bhk"] == bedrooms)]

    if st.session_state.predicted_price is not None:
        col1, col2 = st.columns(2)

        with col1:
            st.metric("Predicted Price", str(st.session_state.predicted_price) + " Lakhs")

        with col2:
            if len(same_type_properties) > 0:
                average_price = same_type_properties["price"].mean()
                difference = round(st.session_state.predicted_price - average_price, 2)
                st.metric(
                    "Average price of similar properties",
                    str(round(average_price, 2)) + " Lakhs",
                    delta=str(difference) + " Lakhs (vs prediction)"
                )
            else:
                st.write("No similar properties found for comparison")

        if st.session_state.verdict is not None:
            st.write("Asking price check:", st.session_state.verdict)

        st.info("Check the other tabs to see similar properties and nearby areas.")


selected_lat = location_info.loc[selected_location, "lat"]
selected_lon = location_info.loc[selected_location, "lon"]


with tab2:
    st.header("Similar Properties in " + selected_location)
    st.write("Existing " + str(bedrooms) + " BHK properties in " + selected_location + " from the dataset")

    min_price = 1
    max_price = int(math.ceil(data["price"].max()))
    price_range = st.slider("Price range (Lakhs)", min_price, max_price, (min_price, max_price), step=1)

    filtered = data[(data["location"] == selected_location) & (data["bhk"] == bedrooms)]
    filtered = filtered[(filtered["price"] >= price_range[0]) & (filtered["price"] <= price_range[1])]

    st.write("Found", len(filtered), "matching properties")

    your_price = st.session_state.predicted_price if st.session_state.predicted_price is not None else 0

    your_property = pd.DataFrame([{
        "lat": selected_lat,
        "lon": selected_lon,
        "location": selected_location + " (Your Property)",
        "bhk": bedrooms,
        "price": your_price,
        "total_sqft_clean": size_sqft
    }])

    # your property is drawn first and bigger, so the red listings
    # sit on top of it and stay visible even at the same coordinates
    layers = [pdk.Layer(
        "ScatterplotLayer",
        data=your_property,
        get_position="[lon, lat]",
        get_radius=200,
        get_fill_color=[60, 140, 255],
        pickable=True,
    )]

    if len(filtered) > 0:
        layers.append(pdk.Layer(
            "ScatterplotLayer",
            data=filtered,
            get_position="[lon, lat]",
            get_radius=60,
            get_fill_color=[255, 60, 60],
            pickable=True,
        ))

    st.write("Blue = your property, red = similar listings. Hover over a dot for details.")

    st.pydeck_chart(pdk.Deck(
        layers=layers,
        initial_view_state=pdk.ViewState(latitude=selected_lat, longitude=selected_lon, zoom=13),
        tooltip={
            "html": "<b>{location}</b><br/>{bhk} BHK<br/>Price: {price} Lakhs<br/>Size: {total_sqft_clean} sqft",
            "style": {"color": "white"}
        },
    ))

    for index, row in filtered.head(20).iterrows():
        st.markdown("---")
        st.write(str(row["bhk"]) + " BHK in " + row["location"])
        st.write("Price:", row["price"], "Lakhs")
        st.write("Size:", row["total_sqft_clean"], "sqft")


with tab3:
    st.header("Nearby Neighborhoods")
    st.write("Areas closest to " + selected_location)

    nearby_list = []
    for loc_name, row in location_info.iterrows():
        if loc_name == selected_location:
            continue
        d = distance_km(selected_lat, selected_lon, row["lat"], row["lon"])
        nearby_list.append({"Neighborhood": loc_name, "distance_number": d})

    nearby_df = pd.DataFrame(nearby_list).sort_values("distance_number").head(10)
    nearby_df["Distance"] = nearby_df["distance_number"].apply(lambda x: str(round(x, 1)) + " km")
    nearby_df = nearby_df[["Neighborhood", "Distance"]]

    st.table(nearby_df)


with tab4:
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

import streamlit as st
import pandas as pd
import pydeck as pdk
import requests
import math

# a bit of custom styling - streamlit's config file only does flat colours,
# so the gradient and the card shadows have to be done with css
st.markdown("""
<style>
.stApp {
    background: linear-gradient(165deg, #37565201 0%, #2C4643 0%, #243A38 100%);
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

    # build a description using only real numbers from the dataset
    area_properties = data[data["location"] == selected_location]
    area_avg_per_sqft = (area_properties["price"] / area_properties["total_sqft_clean"]).mean()

    sqft_per_bedroom = round(size_sqft / bedrooms)

    description = (
        "This is a " + str(bedrooms) + " BHK, " + str(bathrooms) + " bathroom property "
        + "covering " + str(size_sqft) + " sqft in " + selected_location + ", "
        + "which works out to about " + str(sqft_per_bedroom) + " sqft per bedroom. "
    )

    description += (
        "The nearest school is " + format_distance(dist_school) + " away, "
        + "the nearest hospital " + format_distance(dist_hospital) + ", and "
        + "the nearest transit stop " + format_distance(dist_transit) + ". "
    )

    if len(area_properties) > 0:
        description += (
            "There are " + str(len(area_properties)) + " listings in this area in our dataset, "
            + "with an average of " + str(round(area_avg_per_sqft * 100000)) + " rupees per sqft."
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
            "In " + selected_location + ": " + str(ready_percent) + "% of listings are ready to move, "
            + "most are " + common_type_text + ", and prices range from "
            + str(cheapest) + " to " + str(dearest) + " Lakhs."
        )

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
            # our model's average error on test data is 23.7%, so the range
            # scales with the price instead of being a flat amount
            error_percent = 23.7
            margin = st.session_state.predicted_price * error_percent / 100
            low = max(1, round(st.session_state.predicted_price - margin))
            high = round(st.session_state.predicted_price + margin)
            st.metric("Estimated Price Range", str(low) + " - " + str(high) + " Lakhs")
            st.caption(
                "Best estimate: " + str(st.session_state.predicted_price)
                + " Lakhs (our model is off by about 24% on average)"
            )

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

    # every property in a location shares the same coordinates, so they would
    # all stack into one dot. spread them in a small circle around the real
    # point so each one can be seen and hovered separately
    filtered = filtered.copy()
    if len(filtered) > 0:
        spread = 0.004
        angles = [2 * math.pi * i / len(filtered) for i in range(len(filtered))]
        filtered["lat"] = [lat + spread * math.cos(a) for lat, a in zip(filtered["lat"], angles)]
        filtered["lon"] = [lon + spread * math.sin(a) for lon, a in zip(filtered["lon"], angles)]

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
        get_radius=60,
        get_fill_color=[60, 140, 255],
        pickable=True,
    )]

    if len(filtered) > 0:
        layers.append(pdk.Layer(
            "ScatterplotLayer",
            data=filtered,
            get_position="[lon, lat]",
            get_radius=25,
            get_fill_color=[255, 60, 60],
            pickable=True,
        ))

    st.write("The blue marker is the area you selected. Zoom in for a closer look.")

    # only keep the first layer (your property). the red listing dots were all
    # at the same area point, so they drew as one big circle instead of separate dots
    layers = layers[:1]

    st.pydeck_chart(pdk.Deck(
        layers=layers,
        map_style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
        initial_view_state=pdk.ViewState(latitude=selected_lat, longitude=selected_lon, zoom=12),
        tooltip={
            "html": "<b>{location}</b><br/>{bhk} BHK<br/>Price: {price} Lakhs<br/>Size: {total_sqft_clean} sqft",
            "style": {"color": "white"}
        },
    ))

    # asking the API for an estimate per listing means one request each,
    # so it is off by default and only runs when the user wants it
    show_estimates = st.checkbox("Show our estimate for each listing")

    # small helper so distances read as 1.6 km instead of 1.63492
    def listing_distance(value):
        if value is None or pd.isna(value):
            return "not found"
        return str(round(float(value), 1)) + " km"

    for index, row in filtered.head(20).iterrows():

        per_sqft = round(row["price"] * 100000 / row["total_sqft_clean"])

        # each property gets its own bordered card so they do not run together
        with st.container(border=True):

            st.markdown("### " + str(int(row["bhk"])) + " BHK in " + row["location"])

            # the three main numbers, side by side
            col1, col2, col3 = st.columns(3)
            col1.metric("Listed price", str(row["price"]) + " Lakhs")
            col2.metric("Size", str(int(row["total_sqft_clean"])) + " sqft")
            col3.metric("Rate", str(per_sqft) + " /sqft")

            # work out the detail text first, so the columns stay readable
            if not pd.isna(row.get("bath")):
                bath_text = str(int(row["bath"]))
            else:
                bath_text = "not given"

            if not pd.isna(row.get("balcony")):
                balcony_text = str(int(row["balcony"]))
            else:
                balcony_text = "not given"

            if not pd.isna(row.get("area_type")):
                area_text = str(row["area_type"]).strip().replace(" Area", "")
            else:
                area_text = "not given"

            if not pd.isna(row.get("availability")):
                avail = str(row["availability"]).strip()
                if avail == "Ready To Move":
                    avail_text = "Ready to move"
                else:
                    avail_text = "Possession " + avail
            else:
                avail_text = "not given"

            col4, col5, col6, col7 = st.columns(4)
            col4.markdown("**Bathrooms**  \n" + bath_text)
            col5.markdown("**Balconies**  \n" + balcony_text)
            col6.markdown("**Area type**  \n" + area_text)
            col7.markdown("**Status**  \n" + avail_text)

            st.markdown("**What is nearby**")
            col8, col9, col10 = st.columns(3)
            col8.markdown("School  \n" + listing_distance(row.get("dist_to_school_km")))
            col9.markdown("Hospital  \n" + listing_distance(row.get("dist_to_hospital_km")))
            col10.markdown("Transit  \n" + listing_distance(row.get("dist_to_transit_km")))

            if not pd.isna(row.get("society")) and str(row["society"]).strip() != "":
                st.caption("Society: " + str(row["society"]).strip())

            if show_estimates:
                listing_request = {
                    "location": row["location"],
                    "size_sqft": float(row["total_sqft_clean"]),
                    "bedrooms": int(row["bhk"]),
                    "bathrooms": float(row["bath"]) if not pd.isna(row["bath"]) else 2.0,
                    "asking_price": float(row["price"])
                }
                try:
                    listing_response = requests.post("http://127.0.0.1:8000/predict", json=listing_request)
                    listing_result = listing_response.json()
                    st.info(
                        "Our estimate: " + str(listing_result["predicted_price"]) + " Lakhs  -  "
                        + str(listing_result.get("verdict", ""))
                    )
                except:
                    st.caption("Could not get an estimate for this listing")


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

    # price per sqft in each area, so the user can see where they get more space
    area_rates = (data["price"] / data["total_sqft_clean"]).groupby(data["location"]).median() * 100000
    selected_rate = area_rates.get(selected_location)

    def rate_text(area):
        rate = area_rates.get(area)
        if pd.isna(rate):
            return "no data"
        return str(int(round(rate))) + " /sqft"

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
            selected_location + " averages about "
            + str(int(round(selected_rate))) + " rupees per sqft."
        )

    st.table(nearby_df)
    st.caption("Median price per sqft from listings in our dataset.")


with tab4:
    st.header("What Drives the Price?")
    st.write(
        "We used SHAP to measure how much each factor affects the predicted price "
        "across all 11,272 properties in our dataset."
    )

    try:
        importance = pd.read_csv("reports/shap_feature_importance.csv")

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

        st.write(
            "Property features (size, bedrooms, bathrooms) account for about 70% of the "
            "price effect. Location features account for about 30%. Within location, which "
            "area a property is in matters much more than how close it is to any single amenity."
        )
    except:
        st.write("Run the SHAP analysis script to see feature importance here.")

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

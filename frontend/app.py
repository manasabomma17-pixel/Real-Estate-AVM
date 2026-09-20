import streamlit as st
import requests

st.title("Real Estate AVM - Price Predictor")
st.write("Enter property details to get a predicted price (Bangalore)")

size_sqft = st.number_input("Size (sqft)", min_value=100, value=1000, step=50)
bedrooms = st.number_input("Bedrooms (BHK)", min_value=1, value=2, step=1)
bathrooms = st.number_input("Bathrooms", min_value=1, value=2, step=1)

dist_school = st.number_input("Distance to nearest school (km)", min_value=0, value=1, step=1)
dist_hospital = st.number_input("Distance to nearest hospital (km)", min_value=0, value=1, step=1)
dist_transit = st.number_input("Distance to nearest transit (km)", min_value=0, value=1, step=1)

if st.button("Predict Price"):
    data = {
        "property": {
            "size_sqft": size_sqft,
            "bedrooms": bedrooms,
            "bathrooms": bathrooms
        },
        "location": {
            "distance_to_school_km": dist_school,
            "distance_to_hospital_km": dist_hospital,
            "distance_to_transit_km": dist_transit
        }
    }

    try:
        response = requests.post("http://127.0.0.1:8000/predict", json=data)
        result = response.json()
        st.success("Predicted Price: " + str(result["predicted_price"]) + " Lakhs")
    except:
        st.error("Could not connect to the backend. Make sure the FastAPI server is running.")

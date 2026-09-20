import pandas as pd
import time
from geopy.geocoders import Nominatim

data = pd.read_csv("data/raw/bangalore/Bengaluru_House_Data.csv")
print("Loaded rows:", len(data))

# clean up the size column, e.g "2 BHK" becomes 2
def get_bhk(size_text):
    if pd.isna(size_text):
        return None
    number = str(size_text).split(" ")[0]
    try:
        return float(number)
    except:
        return None

data["bhk"] = data["size"].apply(get_bhk)

# clean up total_sqft, sometimes it's a range like "1200-1400"
def get_sqft(sqft_text):
    sqft_text = str(sqft_text)
    if "-" in sqft_text:
        parts = sqft_text.split("-")
        try:
            return (float(parts[0]) + float(parts[1])) / 2
        except:
            return None
    try:
        return float(sqft_text)
    except:
        return None

data["total_sqft_clean"] = data["total_sqft"].apply(get_sqft)

data = data.dropna(subset=["bhk", "total_sqft_clean", "price", "location"])
print("Rows after cleaning:", len(data))

# remove rows where sqft per bedroom looks unrealistic
data = data[data["total_sqft_clean"] / data["bhk"] >= 200]
print("Rows after removing bad sqft/bedroom ratio:", len(data))

data["location"] = data["location"].str.strip()

# geocode each unique location, only once per location not once per row
unique_locations = data["location"].unique()
print("Unique locations to geocode:", len(unique_locations))

geolocator = Nominatim(user_agent="real-estate-avm-project", timeout=10)

location_coords = {}
for i, loc in enumerate(unique_locations):
    print(i + 1, "/", len(unique_locations), "-", loc)
    try:
        result = geolocator.geocode(loc + ", Bangalore, Karnataka, India")
        if result:
            location_coords[loc] = (result.latitude, result.longitude)
        else:
            location_coords[loc] = (None, None)
    except:
        location_coords[loc] = (None, None)
    time.sleep(1)  # wait between requests so we don't overload the server

data["lat"] = data["location"].apply(lambda x: location_coords[x][0])
data["lon"] = data["location"].apply(lambda x: location_coords[x][1])

data = data.dropna(subset=["lat", "lon"])
print("Rows after geocoding:", len(data))

data.to_csv("data/processed/bangalore_sales_clean.csv", index=False)
print("Saved cleaned file!")

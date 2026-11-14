"""
Practical suggestions for a user after a price estimate.

Every suggestion is worked out from real numbers: the API's estimate and
range, and the listings in our dataset. Nothing here is made up or generic.
The functions only use pandas, so they can be tested without Streamlit.
"""

import math

import pandas as pd

# below this many listings, area averages are too shaky to compare against
MIN_LISTINGS = 5


def distance_km(lat1, lon1, lat2, lon2):
    """haversine distance between two points on the earth, in km"""
    R = 6371
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def clean_name(name):
    """'Banaswadi,' and 'banaswadi' are the same place"""
    return " ".join(str(name).strip().strip(",.").split()).lower()


def distance_text(km):
    if km < 0.05:
        return "under 50 m"
    if km < 1:
        return str(int(round(km * 1000))) + " m"
    return str(round(km, 1)) + " km"


def rupees(value):
    """14000 -> '₹14,000' (Indian grouping: 1,23,456)"""
    digits = str(int(round(value)))
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        head = ",".join([head[max(i - 2, 0):i] for i in range(len(head), 0, -2)][::-1])
        digits = head + "," + tail
    return "₹" + digits


def money(lakhs):
    """85.4 -> '₹85 L', 156.6 -> '₹1.57 Cr' (1 Crore = 100 Lakh), as the website shows prices"""
    if lakhs >= 100:
        return "₹" + format(lakhs / 100, ".2f") + " Cr"
    return "₹" + str(round(lakhs)) + " L"


def area_rates(data):
    """median price per sqft (in rupees) and listing count for every area"""
    rate = data["price"] / data["total_sqft_clean"] * 100000
    return pd.DataFrame({
        "rate": rate.groupby(data["location"]).median(),
        "listings": data.groupby("location").size(),
    })


def cheaper_nearby_areas(location, location_info, rates, max_km=5, min_saving_percent=10, limit=3):
    """areas within max_km whose typical price per sqft is clearly lower.
    returns a list of (area name, distance in km, median rate)"""
    if location not in rates.index or location not in location_info.index:
        return []

    own_rate = rates.loc[location, "rate"]
    own_lat = location_info.loc[location, "lat"]
    own_lon = location_info.loc[location, "lon"]

    candidates = []
    for area, row in location_info.iterrows():
        if clean_name(area) == clean_name(location) or area not in rates.index:
            continue
        if rates.loc[area, "listings"] < MIN_LISTINGS:
            continue

        km = distance_km(own_lat, own_lon, row["lat"], row["lon"])
        saving = (1 - rates.loc[area, "rate"] / own_rate) * 100
        if 0.1 < km <= max_km and saving >= min_saving_percent:
            candidates.append((area, km, rates.loc[area, "rate"]))

    candidates.sort(key=lambda c: c[1])  # closest first
    return candidates[:limit]


def build_suggestions(request, result, data, location_info, nearby_estimates=None, named_places=None,
                      exact_distances=None, rate_factor=1.0):
    """
    request: what the user asked for (location, size_sqft, bedrooms, bathrooms,
             optional asking_price)
    result: the API's /predict response
    data: the full listings dataset
    location_info: the location lookup (indexed by area name)
    nearby_estimates: list of (area, km, median rate, estimate in Lakhs) for
             cheaper areas nearby, already priced by the API
    named_places: optional {"school": text, "hospital": text, "transit": text}
             with the names of the nearest places, when we have them
    exact_distances: optional {"school": km, "hospital": km, "transit": km}
             measured from the flat's exact location, when the user gave one
    rate_factor: how much this area's prices have risen since our 2017-19
             data, so area rates are compared at today's level

    returns a list of (kind, title, text). kind is "good", "warning" or "info",
    so the app can pick a colour
    """
    suggestions = []

    location = request["location"]
    size = float(request["size_sqft"])
    bedrooms = int(request["bedrooms"])
    bathrooms = float(request["bathrooms"])
    asking = request.get("asking_price")

    estimate = result["predicted_price"]
    low = result["price_low"]
    high = result["price_high"]

    area_rows = data[data["location"] == location]
    rates = area_rates(data)

    # every tip is a short title and one or two short sentences in plain words

    # 1. the asking price: what to offer
    if asking:
        difference = (asking - estimate) / estimate * 100
        if difference > 10:
            suggestions.append(("warning", "Ask for a lower price",
                                "Seller asks " + str(round(difference)) + "% more than our price. Offer about "
                                + money(estimate) + ". Do not pay more than " + money(high) + "."))
        elif difference < -10:
            suggestions.append(("good", "Cheap price: find out why",
                                "Seller asks " + str(round(abs(difference))) + "% less than our price. Check the papers, "
                                "the building and any unpaid dues. Visit the flat."))
        else:
            suggestions.append(("good", "Price is fair",
                                "Seller's price is close to ours. You can still ask for 2 to 5% off."))
    else:
        suggestions.append(("info", "Add the seller's price",
                            "Add the seller's price to see if it is fair."))

    # 2. value for money compared with the area
    if len(area_rows) >= MIN_LISTINGS:
        area_rate = rates.loc[location, "rate"] * rate_factor
        our_rate = result.get("price_per_sqft", estimate * 100000 / size)
        if asking:
            asked_rate = asking * 100000 / size
            gap = (asked_rate - area_rate) / area_rate * 100
            if gap > 15:
                suggestions.append(("warning", "Costly for this area",
                                    "Seller asks " + rupees(asked_rate) + " per sqft. Usual here: "
                                    + rupees(round(area_rate, -2)) + "."))
            elif gap < -15:
                suggestions.append(("good", "Cheap for this area",
                                    "Seller asks " + rupees(asked_rate) + " per sqft. Usual here: "
                                    + rupees(round(area_rate, -2)) + "."))
        else:
            suggestions.append(("info", "Usual price here",
                                rupees(round(area_rate, -2)) + " per sqft in " + location + ". This flat: "
                                + rupees(our_rate) + " per sqft."))

    # 3. size compared with similar flats
    same_bhk = area_rows[area_rows["bhk"] == bedrooms]
    where = "here"
    if len(same_bhk) < MIN_LISTINGS:
        same_bhk = data[data["bhk"] == bedrooms]
        where = "in Bangalore"
    if len(same_bhk) >= MIN_LISTINGS:
        typical = same_bhk["total_sqft_clean"].median()
        gap = (size - typical) / typical * 100
        if gap < -15:
            suggestions.append(("warning", "Smaller than usual",
                                str(int(size)) + " sqft. Usual " + str(bedrooms) + " BHK " + where + ": "
                                + str(int(typical)) + " sqft. Check the room sizes."))
        elif gap > 15:
            suggestions.append(("good", "Bigger than usual",
                                str(int(size)) + " sqft. Usual " + str(bedrooms) + " BHK " + where + ": "
                                + str(int(typical)) + " sqft."))

    # 4. bathrooms
    if bathrooms < bedrooms and bedrooms >= 2:
        suggestions.append(("info", "Fewer bathrooms",
                            "Less than one bathroom per bedroom. This can lower the resale price."))

    # 5. everyday access: schools, hospitals, transit
    if exact_distances is None and len(area_rows) > 0 and area_rows["dist_to_transit_km"].isna().all():
        suggestions.append(("info", "Check schools and transport yourself",
                            "We have no map data for " + location + "."))
    elif exact_distances is not None or location in location_info.index:
        if exact_distances is not None:
            school, hospital, transit = (exact_distances["school"], exact_distances["hospital"],
                                         exact_distances["transit"])
        else:
            school = location_info.loc[location, "dist_to_school_km"]
            hospital = location_info.loc[location, "dist_to_hospital_km"]
            transit = location_info.loc[location, "dist_to_transit_km"]
        far = []
        if transit > 1:
            far.append("Bus or metro: " + distance_text(transit) + ".")
        if school > 2:
            far.append("School: " + distance_text(school) + ".")
        if hospital > 2:
            far.append("Hospital: " + distance_text(hospital) + ".")
        if far:
            suggestions.append(("warning", "Far from daily needs", " ".join(far)))
        elif max(school, hospital, transit) <= 1:
            text = "School, hospital and bus or metro within 1 km."
            names = [t for t in (named_places or {}).values() if t]
            if names:
                text += " Nearest: " + "; ".join(names) + "."
            suggestions.append(("good", "Good for daily needs", text))

    # 6. what the local market looks like
    if len(area_rows) >= MIN_LISTINGS:
        ready = (area_rows["availability"].astype(str).str.strip() == "Ready To Move").mean() * 100
        if ready < 50:
            suggestions.append(("warning", "Many flats still being built",
                                "Only " + str(round(ready)) + "% are ready to move in here. Check the builder "
                                "and the RERA number."))
    if len(area_rows) < 10:
        suggestions.append(("info", "Few records here",
                            "Only " + str(len(area_rows)) + " records for " + location + ". Our price may be "
                            "less accurate."))

    # 7. cheaper areas close by, priced for this same flat
    if nearby_estimates:
        lines = [area + " (" + distance_text(km) + "): " + money(other_estimate)
                 for area, km, rate, other_estimate in nearby_estimates]
        suggestions.append(("info", "Cheaper areas nearby",
                            "Same flat costs less in " + "; ".join(lines) + "."))

    # 8. anything the model itself is unsure about
    for warning in result.get("warnings", []):
        suggestions.append(("warning", "Estimate may be less accurate", warning))

    return suggestions

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
    return "Rs " + format(int(round(value)), ",")


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

    # 1. the asking price: what to offer
    if asking:
        difference = (asking - estimate) / estimate * 100
        if difference > 10:
            text = ("The asking price is " + str(round(difference)) + "% above our estimate. "
                    "A reasonable opening offer would be around " + str(round(estimate)) + " Lakhs, "
                    "and paying more than " + str(round(high)) + " Lakhs (the top of our range) "
                    "is hard to justify unless the flat has something extra, such as a high floor, a new "
                    "building or a good view. The Price Comparison tab shows where this asking price "
                    "sits against comparable flats.")
            suggestions.append(("warning", "Negotiate the price down", text))
        elif difference < -10:
            text = ("The asking price is " + str(round(abs(difference))) + "% below our estimate. "
                    "That can be a genuine bargain, but first find out why it is cheap: check the legal "
                    "title, the building's age and condition, the floor, and any pending dues. Do not skip "
                    "a site visit.")
            suggestions.append(("good", "Possibly a good deal, but check why", text))
        else:
            text = ("The asking price is within 10% of our estimate, so it looks fair for this area and "
                    "size. A small discount of 2-5% is still common to ask for.")
            suggestions.append(("good", "Fairly priced", text))
    else:
        suggestions.append(("info", "Check an asking price",
                            "Enter the seller's asking price above to see whether it is fair, and how "
                            "much to offer."))

    # 2. value for money compared with the area
    if len(area_rows) >= MIN_LISTINGS:
        area_rate = rates.loc[location, "rate"] * rate_factor
        our_rate = result.get("price_per_sqft", estimate * 100000 / size)
        if asking:
            asked_rate = asking * 100000 / size
            gap = (asked_rate - area_rate) / area_rate * 100
            if gap > 15:
                suggestions.append(("warning", "Pricier than the area average",
                                    "The asking rate works out to " + rupees(asked_rate) + " per sqft, which is "
                                    + str(round(gap)) + "% above the typical " + rupees(area_rate)
                                    + " per sqft in " + location + "."))
            elif gap < -15:
                suggestions.append(("good", "Cheaper than the area average",
                                    "The asking rate works out to " + rupees(asked_rate) + " per sqft, "
                                    + str(round(abs(gap))) + "% below the typical " + rupees(area_rate)
                                    + " per sqft in " + location + "."))
        else:
            suggestions.append(("info", "Typical rate in this area",
                                "Brought up to today's market, flats in " + location + " typically go for about "
                                + rupees(round(area_rate, -2)) + " per sqft. Our estimate for this flat is "
                                + rupees(our_rate) + " per sqft."))

    # 3. size compared with similar flats
    same_bhk = area_rows[area_rows["bhk"] == bedrooms]
    where = "in " + location
    if len(same_bhk) < MIN_LISTINGS:
        same_bhk = data[data["bhk"] == bedrooms]
        where = "across Bangalore"
    if len(same_bhk) >= MIN_LISTINGS:
        typical = same_bhk["total_sqft_clean"].median()
        gap = (size - typical) / typical * 100
        if gap < -15:
            suggestions.append(("warning", "Smaller than usual",
                                "At " + str(int(size)) + " sqft, this is " + str(round(abs(gap)))
                                + "% smaller than a typical " + str(bedrooms) + " BHK " + where + " ("
                                + str(int(typical)) + " sqft). Check that the rooms are a comfortable size, "
                                "and ask whether the area quoted is carpet or super built-up."))
        elif gap > 15:
            suggestions.append(("good", "More space than usual",
                                "At " + str(int(size)) + " sqft, this is " + str(round(gap))
                                + "% larger than a typical " + str(bedrooms) + " BHK " + where + " ("
                                + str(int(typical)) + " sqft)."))

    # 4. bathrooms
    if bathrooms < bedrooms and bedrooms >= 2:
        suggestions.append(("info", "Fewer bathrooms than bedrooms",
                            "This is common in older or compact flats, but buyers usually prefer at least "
                            "one bathroom per bedroom, which can affect resale value."))

    # 5. everyday access: schools, hospitals, transit
    if exact_distances is None and len(area_rows) > 0 and area_rows["dist_to_transit_km"].isna().all():
        suggestions.append(("info", "Check nearby amenities yourself",
                            "We could not get amenity data for " + location + " from OpenStreetMap, so check "
                            "schools, hospitals and public transport in person."))
    elif exact_distances is not None or location in location_info.index:
        if exact_distances is not None:
            school, hospital, transit = (exact_distances["school"], exact_distances["hospital"],
                                         exact_distances["transit"])
            where = "From the flat's exact location"
        else:
            school = location_info.loc[location, "dist_to_school_km"]
            hospital = location_info.loc[location, "dist_to_hospital_km"]
            transit = location_info.loc[location, "dist_to_transit_km"]
            where = "From the area centre"
        far = []
        if transit > 1:
            far.append("the nearest bus stop or station is " + distance_text(transit) + " away")
        if school > 2:
            far.append("the nearest school is " + distance_text(school) + " away")
        if hospital > 2:
            far.append("the nearest hospital or clinic is " + distance_text(hospital) + " away")
        if far:
            suggestions.append(("warning", "Check your daily travel",
                                where + ", " + "; ".join(far) + ". Make sure this suits your "
                                "commute and family needs."))
        elif max(school, hospital, transit) <= 1:
            text = ("A school, a hospital or clinic, and public transport are all within 1 km of the "
                    + ("flat." if exact_distances is not None else "area centre."))
            names = [t for t in (named_places or {}).values() if t]
            if names:
                text += " Nearest: " + "; ".join(names) + "."
            suggestions.append(("good", "Good everyday access", text))

    # 6. what the local market looks like
    if len(area_rows) >= MIN_LISTINGS:
        ready = (area_rows["availability"].astype(str).str.strip() == "Ready To Move").mean() * 100
        if ready < 50:
            suggestions.append(("warning", "Lots of under-construction flats here",
                                "Only " + str(round(ready)) + "% of listings in " + location + " are ready to move. "
                                "If this flat is under construction, check the builder's track record, its RERA "
                                "registration and the promised possession date."))
    if len(area_rows) < 10:
        suggestions.append(("info", "Limited data for this area",
                            "We have only " + str(len(area_rows)) + " listings for " + location + ", so treat the "
                            "estimate with extra caution and compare with recent local deals."))

    # 7. cheaper areas close by, priced for this same flat
    if nearby_estimates:
        lines = []
        for area, km, rate, other_estimate in nearby_estimates:
            saving = estimate - other_estimate
            line = (area + " (" + distance_text(km) + " away): about " + str(round(other_estimate, 1))
                    + " Lakhs for the same flat")
            if saving > 0:
                line += ", roughly " + str(round(saving, 1)) + " Lakhs less"
            lines.append(line)
        suggestions.append(("info", "Cheaper areas nearby",
                            "If the budget is tight, the same flat in these nearby areas is estimated lower: "
                            + "; ".join(lines) + "."))

    # 8. anything the model itself is unsure about
    for warning in result.get("warnings", []):
        suggestions.append(("warning", "Estimate less reliable", warning))

    return suggestions

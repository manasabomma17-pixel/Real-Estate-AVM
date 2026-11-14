"""
Reads the details of a flat out of listing text copied from any property site,
for example:

    "2 BHK Flat for sale in Whitefield, Bangalore. 1,150 sq.ft, 2 bathrooms.
     Price: Rs 85 Lac"

so the user does not have to type them in. Only plain pandas-free Python, so it
can be tested on its own.
"""

import re


def _number(text):
    return float(text.replace(",", ""))


def find_bedrooms(text):
    # "2 BHK", "2-bhk", "3 bedrooms", or label first as on many pages: "Bedrooms: 3"
    match = re.search(r"(\d+)[\s\-_]*(?:bhk|rk|bed(?:room)?s?\b)", text, re.IGNORECASE) \
        or re.search(r"\bbed(?:room)?s?\s*[:\-]?\s*(\d+)\b", text, re.IGNORECASE)
    return int(match.group(1)) if match else None


def find_bathrooms(text):
    # "2 bathrooms", or label first as on many pages: "Bathrooms 2", "Bathrooms: 2"
    match = re.search(r"(\d+)[\s\-_]*(?:bath(?:room)?s?|toilets?)\b", text, re.IGNORECASE) \
        or re.search(r"\b(?:bath(?:room)?s?|toilets?)\s*[:\-]?\s*(\d+)\b", text, re.IGNORECASE)
    return int(match.group(1)) if match else None


def find_size_sqft(text):
    """the area in sqft. square metres and square yards are converted"""
    patterns = [
        (r"([\d,]+(?:\.\d+)?)[\s\-_]*(?:sq\.?\s*ft|sqft|sq\s*feet|square\s*feet|sft)", 1),
        (r"([\d,]+(?:\.\d+)?)\s*(?:sq\.?\s*m\b|sqm|square\s*met(?:er|re)s?)", 10.7639),
        (r"([\d,]+(?:\.\d+)?)\s*(?:sq\.?\s*yd|sq\s*yards?|square\s*yards?)", 9),
    ]
    for pattern, to_sqft in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return round(_number(match.group(1)) * to_sqft)
    return None


def find_price_lakhs(text):
    """the price in Lakhs. understands '85 Lac', '85 Lakhs', '1.2 Cr',
    '1.2 Crore' and full amounts like 'Rs 85,00,000'"""
    crore = re.search(r"(\d+(?:\.\d+)?)\s*(?:cr\b|crores?)", text, re.IGNORECASE)
    if crore:
        return round(_number(crore.group(1)) * 100, 2)

    lakh = re.search(r"(\d+(?:\.\d+)?)\s*(?:l\b|lac\b|lacs\b|lakhs?\b|lakh\b)", text, re.IGNORECASE)
    if lakh:
        return round(_number(lakh.group(1)), 2)

    # a full rupee amount after a currency sign, e.g. Rs 85,00,000 or 8500000
    full = re.search(r"(?:₹|rs\.?|inr)\s*([\d,]{6,})", text, re.IGNORECASE)
    if full:
        return round(_number(full.group(1)) / 100000, 2)
    return None


def find_location(text, known_locations):
    """the longest known area name that appears in the text, so
    'Electronic City Phase II' wins over 'Electronic City'"""
    lowered = " " + re.sub(r"[^a-z0-9]+", " ", text.lower()) + " "
    best = None
    for location in known_locations:
        name = re.sub(r"[^a-z0-9]+", " ", str(location).lower()).strip()
        if len(name) < 3:
            continue
        if " " + name + " " in lowered and (best is None or len(name) > len(best[1])):
            best = (location, name)
    return best[0] if best else None


def is_link(text):
    """true when the user pasted a web address instead of the listing's text"""
    return bool(re.match(r"\s*(https?://|www\.)\S+\s*$", text, re.IGNORECASE))


def parse_listing(text, known_locations):
    """everything that could be found. a value is None if it was not found"""
    return {
        "location": find_location(text, known_locations),
        "bedrooms": find_bedrooms(text),
        "bathrooms": find_bathrooms(text),
        "size_sqft": find_size_sqft(text),
        "asking_price": find_price_lakhs(text),
    }


MONTHS = {"jan": "January", "feb": "February", "mar": "March", "apr": "April", "may": "May", "jun": "June",
          "jul": "July", "aug": "August", "sep": "September", "oct": "October", "nov": "November",
          "dec": "December"}


def availability_text(value):
    """turns the dataset's availability column into plain words.

    the dataset writes possession dates as YEAR-MONTH: '18-May' means May 2018,
    not the 18th of May. we know this because the number is always between 14
    and 22 (the years 2014-2022), never up to 31 as a day would be"""
    value = str(value).strip()
    if value == "Ready To Move":
        return "Ready to move"
    if value == "Immediate Possession":
        return "Immediate possession"
    match = re.match(r"^(\d{2})-([A-Za-z]{3})$", value)
    if match and match.group(2).lower() in MONTHS:
        return "Possession " + MONTHS[match.group(2).lower()] + " 20" + match.group(1)
    return value if value and value != "nan" else "not given"

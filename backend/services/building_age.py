"""
How a building's age affects a flat's price, and what to check for its age.

Our training data has no building age, so the model cannot learn this. Instead
this file applies the standard method Indian registered valuers use, and the
app shows the result separately from the model's estimate, as a rough guide:

    depreciation % = age / life x (100% - salvage value)

with a 60-year life and 10% salvage value for an RCC building. Only the
building wears out, not the land under it, so the depreciation is applied to
the cost of rebuilding the flat (its size x today's construction cost per
sqft), not to the whole price.
"""

import re

BUILDING_LIFE_YEARS = 60
SALVAGE_SHARE = 0.10

# standard-quality construction in Bangalore costs roughly Rs 2,100-2,600 per
# sqft in 2026; we use a round figure in that range
CONSTRUCTION_COST_PER_SQFT = 2500


def depreciation_share(age_years):
    """the share of the building's value lost with age, from 0 to 0.9"""
    age = min(max(age_years, 0), BUILDING_LIFE_YEARS)
    return age / BUILDING_LIFE_YEARS * (1 - SALVAGE_SHARE)


def age_adjustment(size_sqft, age_years, price_lakhs):
    """the rough fall in value for a building of this age, in Lakhs"""
    rebuild_lakhs = size_sqft * CONSTRUCTION_COST_PER_SQFT / 100000
    share = depreciation_share(age_years)
    deduction = rebuild_lakhs * share
    return {
        "years": age_years,
        "depreciation_percent": round(share * 100, 1),
        "rebuild_cost_lakhs": round(rebuild_lakhs, 2),
        "deduction_lakhs": round(deduction, 2),
        "adjusted_price": round(max(price_lakhs - deduction, 1.0), 2),
        "cost_per_sqft": CONSTRUCTION_COST_PER_SQFT,
    }


def age_suggestions(age_years, under_construction):
    """what to check for a flat of this age, as (kind, title, text)"""
    if under_construction:
        return [("warning", "Still being built",
                 "Check the RERA number and the handover date. Look at the builder's old projects. Pay in stages.")]
    if age_years is None:
        return []
    if age_years <= 5:
        return [("good", "New building",
                 "Ask for the occupancy certificate (OC).")]
    if age_years <= 15:
        return [("info", "Ask about upkeep",
                 "Ask about recent repairs and the monthly maintenance charge.")]
    if age_years <= 30:
        return [("warning", "Older building",
                 "Check for leaks and cracks. Check the lift, pipes and wiring.")]
    return [("warning", "Very old building",
             "Get an engineer to check the building. Banks may give a smaller loan.")]

def find_building_age(text):
    """reads the age from listing text: '8 years old', 'Age of property: 5 years',
    or 'under construction'. returns (age in years or None, under construction?)"""
    if re.search(r"under[\s\-]*construction", text, re.IGNORECASE):
        return None, True
    if re.search(r"\b(?:new\s+launch|brand[\s\-]*new|newly\s+built)\b", text, re.IGNORECASE):
        return 0, False
    match = re.search(r"(\d{1,2})\s*\+?\s*(?:years?|yrs?)\s*old", text, re.IGNORECASE) \
        or re.search(r"age(?:\s+of\s+(?:the\s+)?(?:property|building|construction))?\s*[:\-]?\s*(\d{1,2})\s*(?:\+\s*)?(?:years?|yrs?)",
                     text, re.IGNORECASE)
    if match:
        return int(match.group(1)), False
    return None, False

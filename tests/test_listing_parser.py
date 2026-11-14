"""Checks that listing text copied from property sites is read correctly."""

from backend.services.listing_parser import parse_listing

AREAS = ["Whitefield", "Electronic City", "Electronic City Phase II", "Jayanagar", "HSR Layout"]


def test_typical_listing():
    text = "2 BHK Flat for sale in Whitefield, Bangalore. 1,150 sq.ft, 2 bathrooms. Price: Rs 85 Lac"
    assert parse_listing(text, AREAS) == {
        "location": "Whitefield", "bedrooms": 2, "bathrooms": 2, "size_sqft": 1150, "asking_price": 85.0}


def test_crore_price_and_longest_area_name():
    result = parse_listing("3 BHK Apartment, Electronic City Phase II - 1650 sqft - ₹1.2 Cr", AREAS)
    assert result["location"] == "Electronic City Phase II"
    assert result["asking_price"] == 120.0
    assert result["size_sqft"] == 1650


def test_full_rupee_amount():
    assert parse_listing("Jayanagar 2BHK for Rs. 95,00,000", AREAS)["asking_price"] == 95.0


def test_square_metres_converted():
    assert parse_listing("HSR Layout 2 BHK 100 sq m", AREAS)["size_sqft"] == 1076


def test_missing_values_are_none():
    result = parse_listing("Lovely flat, call now", AREAS)
    assert all(value is None for value in result.values())


def test_area_name_must_be_a_whole_word():
    # part of a longer word must not count as the area name
    assert parse_listing("Flat near Jayanagarapalya", AREAS)["location"] is None


def test_details_from_a_pasted_link():
    from backend.services.listing_parser import is_link
    link = ("https://www.nobroker.in/property/buy/2-bhk-apartment-for-sale-in-whitefield-"
            "bangalore/8aa98dc59ebfe60c019ec13f371e2e3a/detail?nbFr=list-buy")
    result = parse_listing(link, AREAS)
    assert result["location"] == "Whitefield"
    assert result["bedrooms"] == 2
    assert is_link(link)
    assert not is_link("2 BHK in Whitefield, 1200 sqft, Rs 85 Lac")


def test_text_copied_from_a_listing_page():
    # property pages often put the label first, each on its own line
    copied = """2 BHK Flat For Sale In Panathur
    ₹78 Lacs
    Built Up Area
    1,150 sqft
    Bathrooms
    2
    Furnishing Semi"""
    result = parse_listing(copied, ["Panathur"])
    assert result == {"location": "Panathur", "bedrooms": 2, "bathrooms": 2,
                      "size_sqft": 1150, "asking_price": 78.0}


def test_availability_dates_are_year_and_month():
    from backend.services.listing_parser import availability_text
    assert availability_text("18-May") == "Possession May 2018"
    assert availability_text("19-Dec") == "Possession December 2019"
    assert availability_text("Ready To Move") == "Ready to move"
    assert availability_text("Immediate Possession") == "Immediate possession"

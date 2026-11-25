"""
Prints the worked example used in the report and viva guide:
a 1,200 sqft, 2 BHK, 2-bathroom flat in Whitefield, seller asking Rs 1.75 Cr.

Run from the project folder:  python -m backend.models.show_example
"""

from backend.main import PredictionRequest, predict

result = predict(PredictionRequest(location="Whitefield", size_sqft=1200, bedrooms=2, bathrooms=2,
                                   asking_price=175))
print("Base value (average flat):", result.base_price, "Lakhs")
for factor in result.factors:
    print("  %+.2f  %s" % (factor.effect, factor.name))
print("Model price (2017-19):", result.predicted_price, "Lakhs  range", result.price_low, "to", result.price_high)
print("Market factor:", result.market_factor, " Today's price:", result.today_price, "Lakhs",
      " range", result.today_low, "to", result.today_high)
print("Verdict:", result.verdict, "(", result.difference_percent, "% )")

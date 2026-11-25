import pandas as pd

sales = pd.read_csv("data/processed/bangalore_sales_clean.csv")
amenities = pd.read_csv("data/processed/bangalore_amenity_distances.csv")

amenities = amenities[["location", "dist_to_school_km", "dist_to_hospital_km", "dist_to_transit_km"]]

final = sales.merge(amenities, on="location", how="left")

# distance to the nearest metro station (data_processing/add_metro_distance.py)
metro = pd.read_csv("data/processed/metro_distances.csv")[["location", "dist_to_metro_km"]]
final = final.merge(metro, on="location", how="left")

print("Final rows:", len(final))
print("Missing school distance:", final["dist_to_school_km"].isna().sum())
print("Missing hospital distance:", final["dist_to_hospital_km"].isna().sum())
print("Missing transit distance:", final["dist_to_transit_km"].isna().sum())
print("Missing metro distance:", final["dist_to_metro_km"].isna().sum())

final.to_csv("data/processed/bangalore_final_dataset.csv", index=False)
print("Saved final dataset!")

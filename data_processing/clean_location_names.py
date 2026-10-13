import pandas as pd
import difflib

data = pd.read_csv("data/raw/bangalore/Bengaluru_House_Data.csv")
data = data.dropna(subset=["location"])

print("Total rows:", len(data))
print("Unique location names before cleaning:", data["location"].nunique())


# STEP 1: basic cleanup
# removes extra spaces, trailing commas and dots, and makes capitalisation
# consistent, so "rr nagar" and "RR Nagar" become the same name
def basic_clean(name):
    name = str(name).strip()
    name = name.strip(",.")
    name = " ".join(name.split())
    return name.title()


data["location_clean"] = data["location"].apply(basic_clean)

merged_by_cleanup = data["location"].nunique() - data["location_clean"].nunique()
print("Unique names after basic cleanup:", data["location_clean"].nunique())
print("Duplicates merged by basic cleanup:", merged_by_cleanup)


# STEP 2: find likely typos
# a rare spelling that looks almost identical to a common one is probably a typo
name_counts = data["location_clean"].value_counts()
all_names = name_counts.index.tolist()

suggestions = []

for name in all_names:
    if name_counts[name] > 5:
        continue

    common_names = [n for n in all_names if name_counts[n] > name_counts[name]]
    matches = difflib.get_close_matches(name, common_names, n=1, cutoff=0.85)

    if matches:
        suggestions.append({
            "messy_name": name,
            "appears_times": name_counts[name],
            "suggested_name": matches[0],
            "suggested_appears_times": name_counts[matches[0]]
        })

suggestions_df = pd.DataFrame(suggestions)
print("\nPossible spelling errors found:", len(suggestions_df))

suggestions_df.to_csv("reports/location_name_suggestions.csv", index=False)
print("Saved to reports/location_name_suggestions.csv")

if len(suggestions_df) > 0:
    print("\nExamples:")
    print(suggestions_df.head(15).to_string(index=False))


# STEP 3: entries that are descriptions, not place names
suspicious = [n for n in all_names if len(n.split()) > 5]
print("\nEntries that look like descriptions, not places:", len(suspicious))
for name in suspicious[:10]:
    print("  -", name)

# save the cleaned names so the pipeline can use them later
data[["location", "location_clean"]].drop_duplicates().to_csv(
    "reports/location_name_mapping.csv", index=False
)
print("\nSaved name mapping to reports/location_name_mapping.csv")

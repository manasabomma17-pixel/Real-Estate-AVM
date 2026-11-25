"""
Adds one quarter's Bengaluru house price change, so the site's prices stay current.

Every quarter, look up Bengaluru's quarter-on-quarter change in an official index:
- NHB RESIDEX (National Housing Bank), "HPI @ Assessment Prices", or
- the RBI House Price Index (data.rbi.org.in > Real Sector > Prices & Wages)
then run, from the project folder:

    python -m data_processing.update_price_index --quarter "Oct-Dec 2026" --change 2.4 \
        --source "NHB RESIDEX Q3 FY2026-27" --released 2027-03-15

Commit and push the CSV: Render redeploys and every price moves with it.
Only add quarters after October 2026 (our locality rates already include earlier ones).
"""

import argparse
import csv

from backend.services.market_index import INDEX_PATH, load_updates, multiplier

MAX_CHANGE = 20  # a quarterly move bigger than this is almost surely a typo


def add_quarter(quarter, change, source, released, path=INDEX_PATH):
    quarter = quarter.strip()
    if not quarter or not source.strip():
        raise ValueError("quarter and source are required")
    if abs(change) > MAX_CHANGE:
        raise ValueError("a change of %s%% in one quarter looks wrong; check the number" % change)
    if any(row["quarter"] == quarter for row in load_updates(path)):
        raise ValueError(quarter + " is already in the file")
    with open(path, "a", newline="") as f:
        csv.writer(f).writerow([quarter, change, source.strip(), released.strip()])
    return multiplier(load_updates(path))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quarter", required=True, help='e.g. "Oct-Dec 2026"')
    parser.add_argument("--change", required=True, type=float, help="quarter-on-quarter change in percent, e.g. 2.4")
    parser.add_argument("--source", required=True, help='e.g. "NHB RESIDEX Q3 FY2026-27"')
    parser.add_argument("--released", default="", help="release date, e.g. 2027-03-15")
    args = parser.parse_args()
    total = add_quarter(args.quarter, args.change, args.source, args.released)
    print("Added", args.quarter, "(%+.1f%%)." % args.change, "Prices now x%.3f since October 2026." % total)


if __name__ == "__main__":
    main()

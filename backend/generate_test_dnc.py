"""
Generate a test DNC CSV using real properties from the database.
Picks up to 10 properties with owner data and writes them as DNC records.

Usage:
    cd backend
    python generate_test_dnc.py [--out /path/to/output.csv] [--count 10]
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault("DATABASE_URL", "postgresql://pathfinder:pathfinder@localhost:5432/pathfinder")

from sqlalchemy import select, or_
from app.database import SessionLocal
from app.models.property import Property


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="../sample_dnc_list.csv")
    parser.add_argument("--count", type=int, default=10)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        rows = db.execute(
            select(Property)
            .where(
                or_(
                    Property.owner_email.isnot(None),
                    Property.owner_phone.isnot(None),
                    Property.apn.isnot(None),
                )
            )
            .limit(args.count * 3)
        ).scalars().all()
    finally:
        db.close()

    if not rows:
        print("No properties found in database. Run a scraper or seed first.")
        sys.exit(1)

    # Spread across 5 match types
    records = []
    for i, prop in enumerate(rows[: args.count]):
        match_type = i % 5
        rec: dict[str, str] = {
            "name": "",
            "email": "",
            "phone": "",
            "address": "",
            "apn": "",
        }
        if match_type == 0 and prop.owner_email:
            rec["email"] = prop.owner_email
            rec["name"] = prop.owner_name or ""
        elif match_type == 1 and prop.owner_phone:
            rec["phone"] = prop.owner_phone
            rec["name"] = prop.owner_name or ""
        elif match_type == 2 and prop.apn:
            rec["apn"] = prop.apn
        elif match_type == 3 and prop.address:
            rec["address"] = f"{prop.address} {prop.city} {prop.state}"
        elif prop.owner_name and len(prop.owner_name) >= 4:
            rec["name"] = prop.owner_name
        else:
            rec["apn"] = prop.apn or ""
        records.append(rec)

    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), args.out))
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "email", "phone", "address", "apn"])
        writer.writeheader()
        writer.writerows(records)

    print(f"Written {len(records)} test DNC records → {out_path}")
    print("Upload this file to the DNC module to test matching.")


if __name__ == "__main__":
    main()

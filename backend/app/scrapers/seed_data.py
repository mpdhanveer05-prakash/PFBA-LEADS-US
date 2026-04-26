"""
Seed the database with realistic fake property and assessment data.
Usage:
    docker-compose exec backend python -m app.scrapers.seed_data --county travis_tx --count 200
"""
import argparse
import logging
import random
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.county import County
from app.models.property import Property
from app.models.assessment import Assessment
from app.models.comparable_sale import ComparableSale

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STREET_NAMES = [
    "Oak", "Maple", "Pine", "Cedar", "Elm", "Willow", "Birch", "Walnut",
    "Pecan", "Magnolia", "Sunrise", "Sunset", "Lakeside", "Hilltop", "Creek",
    "River", "Meadow", "Forest", "Valley", "Ridge",
]
STREET_TYPES = ["Dr", "St", "Ave", "Blvd", "Ln", "Ct", "Way", "Pl"]

_FIRST_NAMES = [
    "James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda",
    "William", "Barbara", "David", "Susan", "Richard", "Jessica", "Joseph", "Sarah",
    "Thomas", "Karen", "Charles", "Lisa", "Christopher", "Nancy", "Daniel", "Betty",
    "Matthew", "Margaret", "Anthony", "Sandra", "Mark", "Ashley",
]
_LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson",
]
_EMAIL_DOMAINS = ["gmail.com", "yahoo.com", "outlook.com", "icloud.com", "hotmail.com"]


def _rand_owner() -> tuple[str, str, str]:
    first = random.choice(_FIRST_NAMES)
    last = random.choice(_LAST_NAMES)
    name = f"{first} {last}"
    email = f"{first.lower()}.{last.lower()}{random.randint(1, 99)}@{random.choice(_EMAIL_DOMAINS)}"
    area = random.randint(200, 999)
    phone = f"({area}) {random.randint(200,999)}-{random.randint(1000,9999)}"
    return name, email, phone

COUNTY_CONFIGS = {
    # Texas
    "travis_tx": {
        "state": "TX",
        "cities": ["Austin", "Round Rock", "Cedar Park", "Pflugerville", "Manor"],
        "zip_prefixes": ["787"],
        "lat_range": (30.15, 30.55),
        "lng_range": (-97.95, -97.55),
        "price_per_sqft_range": (180, 380),
        "assessed_ratio_range": (0.80, 1.30),
    },
    "harris_tx": {
        "state": "TX",
        "cities": ["Houston", "Pasadena", "Pearland", "Sugar Land", "Katy", "Spring"],
        "zip_prefixes": ["770", "771", "772"],
        "lat_range": (29.60, 30.10),
        "lng_range": (-95.80, -95.05),
        "price_per_sqft_range": (130, 280),
        "assessed_ratio_range": (0.85, 1.35),
    },
    "dallas_tx": {
        "state": "TX",
        "cities": ["Dallas", "Garland", "Irving", "Mesquite", "Richardson", "Carrollton"],
        "zip_prefixes": ["752", "751"],
        "lat_range": (32.60, 33.05),
        "lng_range": (-97.00, -96.55),
        "price_per_sqft_range": (150, 300),
        "assessed_ratio_range": (0.85, 1.30),
    },
    "tarrant_tx": {
        "state": "TX",
        "cities": ["Fort Worth", "Arlington", "Grand Prairie", "Mansfield", "Euless"],
        "zip_prefixes": ["760", "761"],
        "lat_range": (32.55, 32.95),
        "lng_range": (-97.50, -97.05),
        "price_per_sqft_range": (140, 270),
        "assessed_ratio_range": (0.85, 1.28),
    },
    "bexar_tx": {
        "state": "TX",
        "cities": ["San Antonio", "Converse", "Universal City", "Schertz", "Helotes"],
        "zip_prefixes": ["782", "781"],
        "lat_range": (29.25, 29.75),
        "lng_range": (-98.70, -98.20),
        "price_per_sqft_range": (120, 230),
        "assessed_ratio_range": (0.82, 1.28),
    },
    "collin_tx": {
        "state": "TX",
        "cities": ["Plano", "McKinney", "Frisco", "Allen", "Wylie"],
        "zip_prefixes": ["750", "754"],
        "lat_range": (33.05, 33.45),
        "lng_range": (-96.80, -96.40),
        "price_per_sqft_range": (180, 360),
        "assessed_ratio_range": (0.80, 1.30),
    },
    "denton_tx": {
        "state": "TX",
        "cities": ["Denton", "Lewisville", "Flower Mound", "Frisco", "Little Elm"],
        "zip_prefixes": ["762", "750"],
        "lat_range": (33.10, 33.50),
        "lng_range": (-97.30, -96.85),
        "price_per_sqft_range": (170, 330),
        "assessed_ratio_range": (0.82, 1.28),
    },
    "williamson_tx": {
        "state": "TX",
        "cities": ["Georgetown", "Round Rock", "Cedar Park", "Leander", "Hutto"],
        "zip_prefixes": ["786", "787"],
        "lat_range": (30.40, 30.85),
        "lng_range": (-97.90, -97.50),
        "price_per_sqft_range": (175, 340),
        "assessed_ratio_range": (0.82, 1.32),
    },
    "montgomery_tx": {
        "state": "TX",
        "cities": ["Conroe", "The Woodlands", "Spring", "Magnolia", "Tomball"],
        "zip_prefixes": ["773"],
        "lat_range": (30.10, 30.60),
        "lng_range": (-95.80, -95.30),
        "price_per_sqft_range": (140, 290),
        "assessed_ratio_range": (0.83, 1.30),
    },
    # Florida
    "miami_dade_fl": {
        "state": "FL",
        "cities": ["Miami", "Hialeah", "Miami Gardens", "Coral Gables", "Doral"],
        "zip_prefixes": ["331", "330"],
        "lat_range": (25.55, 25.95),
        "lng_range": (-80.55, -80.15),
        "price_per_sqft_range": (200, 500),
        "assessed_ratio_range": (0.75, 1.40),
    },
    "broward_fl": {
        "state": "FL",
        "cities": ["Fort Lauderdale", "Hollywood", "Pembroke Pines", "Miramar", "Davie"],
        "zip_prefixes": ["330", "333"],
        "lat_range": (25.90, 26.40),
        "lng_range": (-80.60, -80.10),
        "price_per_sqft_range": (190, 450),
        "assessed_ratio_range": (0.78, 1.38),
    },
    "palm_beach_fl": {
        "state": "FL",
        "cities": ["West Palm Beach", "Boca Raton", "Boynton Beach", "Delray Beach", "Jupiter"],
        "zip_prefixes": ["334", "334"],
        "lat_range": (26.35, 26.95),
        "lng_range": (-80.45, -80.00),
        "price_per_sqft_range": (220, 600),
        "assessed_ratio_range": (0.75, 1.38),
    },
    "hillsborough_fl": {
        "state": "FL",
        "cities": ["Tampa", "Brandon", "Riverview", "Temple Terrace", "Plant City"],
        "zip_prefixes": ["336"],
        "lat_range": (27.70, 28.10),
        "lng_range": (-82.70, -82.20),
        "price_per_sqft_range": (170, 380),
        "assessed_ratio_range": (0.78, 1.35),
    },
    "orange_fl": {
        "state": "FL",
        "cities": ["Orlando", "Kissimmee", "Apopka", "Winter Garden", "Ocoee"],
        "zip_prefixes": ["328", "347"],
        "lat_range": (28.25, 28.70),
        "lng_range": (-81.65, -81.10),
        "price_per_sqft_range": (165, 350),
        "assessed_ratio_range": (0.80, 1.35),
    },
    "pinellas_fl": {
        "state": "FL",
        "cities": ["St. Petersburg", "Clearwater", "Largo", "Dunedin", "Tarpon Springs"],
        "zip_prefixes": ["337"],
        "lat_range": (27.75, 28.10),
        "lng_range": (-82.85, -82.60),
        "price_per_sqft_range": (175, 420),
        "assessed_ratio_range": (0.78, 1.35),
    },
    # California
    "san_diego_ca": {
        "state": "CA",
        "cities": ["San Diego", "Chula Vista", "El Cajon", "Escondido", "Santee"],
        "zip_prefixes": ["919", "920"],
        "lat_range": (32.55, 33.10),
        "lng_range": (-117.35, -116.75),
        "price_per_sqft_range": (350, 800),
        "assessed_ratio_range": (0.70, 1.35),
    },
    "los_angeles_ca": {
        "state": "CA",
        "cities": ["Los Angeles", "Long Beach", "Glendale", "Pasadena", "Burbank", "Torrance"],
        "zip_prefixes": ["900", "901", "902", "903"],
        "lat_range": (33.70, 34.80),
        "lng_range": (-118.70, -117.65),
        "price_per_sqft_range": (500, 1200),
        "assessed_ratio_range": (0.65, 1.30),
    },
    "orange_ca": {
        "state": "CA",
        "cities": ["Anaheim", "Santa Ana", "Irvine", "Huntington Beach", "Garden Grove"],
        "zip_prefixes": ["926", "927", "928"],
        "lat_range": (33.45, 33.95),
        "lng_range": (-118.10, -117.40),
        "price_per_sqft_range": (450, 950),
        "assessed_ratio_range": (0.68, 1.30),
    },
    "riverside_ca": {
        "state": "CA",
        "cities": ["Riverside", "Moreno Valley", "Corona", "Temecula", "Murrieta"],
        "zip_prefixes": ["925", "923"],
        "lat_range": (33.55, 34.10),
        "lng_range": (-117.55, -116.05),
        "price_per_sqft_range": (280, 580),
        "assessed_ratio_range": (0.72, 1.32),
    },
    "santa_clara_ca": {
        "state": "CA",
        "cities": ["San Jose", "Sunnyvale", "Santa Clara", "Mountain View", "Palo Alto"],
        "zip_prefixes": ["950", "951"],
        "lat_range": (37.05, 37.50),
        "lng_range": (-122.20, -121.60),
        "price_per_sqft_range": (700, 1800),
        "assessed_ratio_range": (0.62, 1.25),
    },
    # Other states
    "cook_il": {
        "state": "IL",
        "cities": ["Chicago", "Evanston", "Cicero", "Skokie", "Oak Park", "Schaumburg"],
        "zip_prefixes": ["606", "607", "604"],
        "lat_range": (41.45, 42.15),
        "lng_range": (-88.25, -87.55),
        "price_per_sqft_range": (150, 400),
        "assessed_ratio_range": (0.88, 1.40),
    },
    "king_wa": {
        "state": "WA",
        "cities": ["Seattle", "Bellevue", "Kent", "Renton", "Kirkland", "Redmond"],
        "zip_prefixes": ["980", "981", "982"],
        "lat_range": (47.15, 47.80),
        "lng_range": (-122.50, -121.75),
        "price_per_sqft_range": (400, 900),
        "assessed_ratio_range": (0.72, 1.28),
    },
    "maricopa_az": {
        "state": "AZ",
        "cities": ["Phoenix", "Scottsdale", "Tempe", "Mesa", "Chandler", "Glendale"],
        "zip_prefixes": ["850", "852", "853"],
        "lat_range": (33.05, 33.90),
        "lng_range": (-112.90, -111.55),
        "price_per_sqft_range": (175, 380),
        "assessed_ratio_range": (0.80, 1.32),
    },
    "clark_nv": {
        "state": "NV",
        "cities": ["Las Vegas", "Henderson", "North Las Vegas", "Boulder City", "Mesquite"],
        "zip_prefixes": ["891", "890"],
        "lat_range": (35.55, 36.50),
        "lng_range": (-115.45, -114.55),
        "price_per_sqft_range": (180, 380),
        "assessed_ratio_range": (0.80, 1.35),
    },
    "fulton_ga": {
        "state": "GA",
        "cities": ["Atlanta", "Sandy Springs", "Roswell", "Alpharetta", "Johns Creek"],
        "zip_prefixes": ["303", "300"],
        "lat_range": (33.55, 34.05),
        "lng_range": (-84.65, -84.25),
        "price_per_sqft_range": (175, 450),
        "assessed_ratio_range": (0.80, 1.35),
    },
    "mecklenburg_nc": {
        "state": "NC",
        "cities": ["Charlotte", "Concord", "Huntersville", "Matthews", "Mint Hill"],
        "zip_prefixes": ["282"],
        "lat_range": (35.05, 35.50),
        "lng_range": (-81.05, -80.60),
        "price_per_sqft_range": (165, 360),
        "assessed_ratio_range": (0.82, 1.32),
    },
    "wake_nc": {
        "state": "NC",
        "cities": ["Raleigh", "Cary", "Apex", "Wake Forest", "Fuquay-Varina"],
        "zip_prefixes": ["276", "275"],
        "lat_range": (35.55, 36.05),
        "lng_range": (-78.90, -78.40),
        "price_per_sqft_range": (170, 360),
        "assessed_ratio_range": (0.82, 1.30),
    },
    # Verified Socrata counties
    "ny_nyc": {
        "state": "NY",
        "cities": ["Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island"],
        "zip_prefixes": ["100", "101", "102", "104", "103"],
        "lat_range": (40.50, 40.92),
        "lng_range": (-74.26, -73.70),
        "price_per_sqft_range": (500, 2000),
        "assessed_ratio_range": (0.60, 1.20),
    },
    "ca_sf": {
        "state": "CA",
        "cities": ["San Francisco"],
        "zip_prefixes": ["941"],
        "lat_range": (37.70, 37.83),
        "lng_range": (-122.52, -122.36),
        "price_per_sqft_range": (800, 2200),
        "assessed_ratio_range": (0.55, 1.15),
    },
    "pa_philly": {
        "state": "PA",
        "cities": ["Philadelphia"],
        "zip_prefixes": ["191"],
        "lat_range": (39.87, 40.14),
        "lng_range": (-75.28, -74.96),
        "price_per_sqft_range": (120, 400),
        "assessed_ratio_range": (0.75, 1.40),
    },
}

PROPERTY_TYPES = ["RESIDENTIAL"] * 7 + ["COMMERCIAL"] * 2 + ["INDUSTRIAL"]


def _rand_address(cfg: dict) -> tuple[str, str, str]:
    street = f"{random.randint(100, 9999)} {random.choice(STREET_NAMES)} {random.choice(STREET_TYPES)}"
    city = random.choice(cfg["cities"])
    zip_code = random.choice(cfg["zip_prefixes"]) + str(random.randint(10, 99))
    return street, city, zip_code


def _rand_apn(prefix: str) -> str:
    return f"{prefix}-{random.randint(100, 999):03d}-{random.randint(1000, 9999):04d}-{random.randint(10, 99):02d}"


def seed_county(db: Session, county: County, count: int) -> None:
    slug = county.scraper_adapter
    cfg = COUNTY_CONFIGS.get(slug)
    if not cfg:
        logger.error("No seed config for adapter %s", slug)
        return

    logger.info("Seeding %d properties for %s %s...", count, county.name, county.state)

    properties_added = 0
    assessments_added = 0
    comps_added = 0

    # Keep track of all property locations for comparable sales generation
    property_records = []

    for i in range(count):
        apn = _rand_apn(slug[:2].upper())
        address, city, zip_code = _rand_address(cfg)
        prop_type = random.choice(PROPERTY_TYPES)
        sqft = random.randint(800, 4500) if prop_type == "RESIDENTIAL" else random.randint(2000, 20000)
        year_built = random.randint(1960, 2022)
        lat = round(random.uniform(*cfg["lat_range"]), 6)
        lng = round(random.uniform(*cfg["lng_range"]), 6)
        bedrooms = random.randint(2, 6) if prop_type == "RESIDENTIAL" else None
        bathrooms = random.choice([1.0, 1.5, 2.0, 2.5, 3.0]) if prop_type == "RESIDENTIAL" else None
        owner_name, owner_email, owner_phone = _rand_owner()

        prop = Property(
            id=uuid.uuid4(),
            county_id=county.id,
            apn=apn,
            address=address,
            city=city,
            state=cfg["state"],
            zip=zip_code,
            property_type=prop_type,
            building_sqft=sqft,
            lot_size_sqft=sqft + random.randint(500, 5000),
            year_built=year_built,
            bedrooms=bedrooms,
            bathrooms=bathrooms,
            owner_name=owner_name,
            owner_email=owner_email,
            owner_phone=owner_phone,
            latitude=lat,
            longitude=lng,
        )
        db.add(prop)
        properties_added += 1

        # Market value = realistic price per sqft
        ppsf = random.uniform(*cfg["price_per_sqft_range"])
        market_value = ppsf * sqft

        # Assessed value = market × ratio (>1.0 means over-assessed = appeal opportunity)
        assessed_ratio = random.uniform(*cfg["assessed_ratio_range"])
        assessed_total = Decimal(str(round(market_value * assessed_ratio, 2)))
        assessed_land = Decimal(str(round(float(assessed_total) * 0.25, 2)))
        assessed_improvement = assessed_total - assessed_land
        tax_rate = 0.022 if cfg["state"] == "TX" else 0.012
        tax_amount = Decimal(str(round(float(assessed_total) * tax_rate, 2)))

        assessment = Assessment(
            id=uuid.uuid4(),
            property_id=prop.id,
            tax_year=2024,
            assessed_land=assessed_land,
            assessed_improvement=assessed_improvement,
            assessed_total=assessed_total,
            tax_amount=tax_amount,
            data_hash=str(uuid.uuid4()).replace("-", ""),
            fetched_at=datetime.now(timezone.utc),
        )
        db.add(assessment)
        assessments_added += 1

        property_records.append({
            "prop": prop,
            "market_ppsf": ppsf,
            "sqft": sqft,
            "lat": lat,
            "lng": lng,
        })

    db.flush()

    # Generate comparable sales for each property (3-6 comps)
    for rec in property_records:
        num_comps = random.randint(3, 6)
        for _ in range(num_comps):
            comp_sqft = int(rec["sqft"] * random.uniform(0.80, 1.20))
            comp_ppsf = rec["market_ppsf"] * random.uniform(0.85, 1.15)
            comp_price = Decimal(str(round(comp_ppsf * comp_sqft, 2)))
            distance = round(random.uniform(0.05, 0.50), 3)
            sale_year = random.randint(2022, 2024)
            sale_month = random.randint(1, 12)

            comp = ComparableSale(
                id=uuid.uuid4(),
                property_id=rec["prop"].id,
                comp_apn=_rand_apn("CP"),
                sale_price=comp_price,
                sale_date=date(sale_year, sale_month, random.randint(1, 28)),
                sqft=comp_sqft,
                price_per_sqft=Decimal(str(round(comp_ppsf, 2))),
                distance_miles=distance,
                similarity_score=round(random.uniform(0.65, 0.98), 3),
            )
            db.add(comp)
            comps_added += 1

    db.commit()

    # Update last_scraped_at
    county.last_scraped_at = datetime.now(timezone.utc)
    db.commit()

    logger.info(
        "Done: %d properties, %d assessments, %d comparable sales",
        properties_added, assessments_added, comps_added,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed fake property data")
    parser.add_argument("--county", required=True, help="County adapter slug (e.g. travis_tx)")
    parser.add_argument("--count", type=int, default=150, help="Number of properties to generate")
    args = parser.parse_args()

    db: Session = SessionLocal()
    try:
        county = db.query(County).filter(County.scraper_adapter == args.county).first()
        if not county:
            logger.error("County with adapter '%s' not found. Add it via POST /api/counties first.", args.county)
            return
        seed_county(db, county, args.count)
    finally:
        db.close()


if __name__ == "__main__":
    main()

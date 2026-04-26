"""Unit tests for ComparableSalesService — covers edge cases."""
import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.models.county import County
from app.models.property import Property
from app.services.comparable_sales_service import ComparableSalesService, _haversine


def _make_county(db):
    c = County(name="Test", state="TX", portal_url="https://x.com", scraper_adapter="travis_tx")
    db.add(c)
    db.flush()
    return c


def _make_property(db, county_id, **kwargs):
    defaults = dict(
        county_id=county_id,
        apn=str(uuid.uuid4())[:10],
        address="100 Main St",
        city="Austin",
        state="TX",
        zip="78701",
        property_type="RESIDENTIAL",
        building_sqft=2000,
        year_built=2005,
        latitude=30.2672,
        longitude=-97.7431,
    )
    defaults.update(kwargs)
    prop = Property(**defaults)
    db.add(prop)
    db.flush()
    return prop


def _sale(**kwargs):
    defaults = dict(
        comp_apn="999-000",
        sale_price=400000,
        sale_date="2024-01-15",
        sqft=2000,
        price_per_sqft=200,
        property_type="RESIDENTIAL",
        year_built=2005,
        latitude=30.2675,
        longitude=-97.7435,
        zip="78701",
    )
    defaults.update(kwargs)
    return defaults


# --- Haversine ---

def test_haversine_same_point():
    assert _haversine(30.0, -97.0, 30.0, -97.0) == 0.0


def test_haversine_known_distance():
    # ~0.03 miles apart
    d = _haversine(30.2672, -97.7431, 30.2675, -97.7435)
    assert d < 0.05


# --- find_and_store_comps ---

def test_no_comps_found(db):
    county = _make_county(db)
    prop = _make_property(db, county.id)
    svc = ComparableSalesService(db)
    # Different property type — filtered out
    comps = svc.find_and_store_comps(prop.id, [_sale(property_type="COMMERCIAL")])
    assert comps == []


def test_sqft_outside_tolerance_filtered(db):
    county = _make_county(db)
    prop = _make_property(db, county.id, building_sqft=2000)
    svc = ComparableSalesService(db)
    # 2000 * 1.25 = 2500 → outside ±20%
    comps = svc.find_and_store_comps(prop.id, [_sale(sqft=2500)])
    assert comps == []


def test_distance_outside_half_mile_filtered(db):
    county = _make_county(db)
    prop = _make_property(db, county.id, latitude=30.2672, longitude=-97.7431)
    svc = ComparableSalesService(db)
    # Move 5 miles away
    comps = svc.find_and_store_comps(prop.id, [_sale(latitude=30.3400, longitude=-97.7431)])
    assert comps == []


def test_matching_comp_stored(db):
    county = _make_county(db)
    prop = _make_property(db, county.id)
    svc = ComparableSalesService(db)
    comps = svc.find_and_store_comps(prop.id, [_sale()])
    assert len(comps) == 1
    assert comps[0].comp_apn == "999-000"
    assert comps[0].similarity_score > 0


def test_top_5_kept(db):
    county = _make_county(db)
    prop = _make_property(db, county.id)
    svc = ComparableSalesService(db)
    sales = [_sale(comp_apn=f"APN-{i}", sale_price=400000 + i * 1000) for i in range(10)]
    comps = svc.find_and_store_comps(prop.id, sales)
    assert len(comps) == 5


def test_market_value_no_comps(db):
    county = _make_county(db)
    prop = _make_property(db, county.id)
    svc = ComparableSalesService(db)
    assert svc.estimate_market_value(prop.id) is None


def test_market_value_calculated(db):
    county = _make_county(db)
    prop = _make_property(db, county.id, building_sqft=2000)
    svc = ComparableSalesService(db)
    svc.find_and_store_comps(prop.id, [_sale(sqft=2000, sale_price=400000)])
    val = svc.estimate_market_value(prop.id)
    assert val is not None
    assert val == Decimal("400000.00")  # 200 $/sqft × 2000 sqft


def test_outlier_sale_prices(db):
    """Outlier prices should not crash — median smooths them."""
    county = _make_county(db)
    prop = _make_property(db, county.id, building_sqft=2000)
    svc = ComparableSalesService(db)
    sales = [
        _sale(comp_apn="A", sale_price=400000, sqft=2000),
        _sale(comp_apn="B", sale_price=5000000, sqft=2000),  # outlier
        _sale(comp_apn="C", sale_price=380000, sqft=2000),
    ]
    comps = svc.find_and_store_comps(prop.id, sales)
    val = svc.estimate_market_value(prop.id)
    assert val is not None
    # Median of [200, 2500, 190] = 200 → 400000
    assert val < Decimal("600000")

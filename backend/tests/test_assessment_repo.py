import uuid
from decimal import Decimal

from app.models.county import County
from app.models.property import Property
from app.services.assessment_repository import AssessmentRepository


def _make_county(db):
    county = County(
        name="Test County",
        state="TX",
        portal_url="https://example.com",
        scraper_adapter="travis_tx",
    )
    db.add(county)
    db.flush()
    return county


def _make_property(db, county_id):
    prop = Property(
        county_id=county_id,
        apn="123-456-789",
        address="100 Main St",
        city="Austin",
        state="TX",
        zip="78701",
        property_type="RESIDENTIAL",
    )
    db.add(prop)
    db.flush()
    return prop


def test_create_assessment(db):
    county = _make_county(db)
    prop = _make_property(db, county.id)
    repo = AssessmentRepository(db)

    assessment = repo.create(
        property_id=prop.id,
        tax_year=2024,
        assessed_total=Decimal("350000.00"),
        data_hash="abc123",
    )
    assert assessment.id is not None
    assert assessment.assessed_total == Decimal("350000.00")


def test_has_changed_new_record(db):
    county = _make_county(db)
    prop = _make_property(db, county.id)
    repo = AssessmentRepository(db)

    # No assessment exists → always changed
    assert repo.has_changed(prop.id, 2024, "somehash") is True


def test_has_changed_same_hash(db):
    county = _make_county(db)
    prop = _make_property(db, county.id)
    repo = AssessmentRepository(db)

    repo.create(prop.id, 2024, Decimal("100000"), data_hash="fixed-hash")
    assert repo.has_changed(prop.id, 2024, "fixed-hash") is False
    assert repo.has_changed(prop.id, 2024, "different-hash") is True

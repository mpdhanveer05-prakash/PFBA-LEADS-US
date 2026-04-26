def test_list_counties_empty(client):
    resp = client.get("/api/counties")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_and_get_county(client):
    payload = {
        "name": "Travis",
        "state": "TX",
        "portal_url": "https://www.traviscad.org",
        "scraper_adapter": "travis_tx",
        "appeal_deadline_days": 45,
    }
    resp = client.post("/api/counties", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Travis"
    assert data["state"] == "TX"

    county_id = data["id"]
    resp2 = client.get(f"/api/counties/{county_id}")
    assert resp2.status_code == 200
    assert resp2.json()["id"] == county_id

"""Tests for Farmer API."""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    print("✅ test_health passed")


def test_root():
    r = client.get("/")
    assert r.status_code == 200
    print("✅ test_root passed")


def test_list_crops():
    r = client.get("/crops")
    assert r.status_code == 200
    crops = r.json()
    assert "rice" in crops
    assert "wheat" in crops
    print(f"✅ test_list_crops ({len(crops)} crops)")


def test_get_crop_rice():
    r = client.get("/crops/rice")
    assert r.status_code == 200
    data = r.json()
    assert data["found"] is True
    assert data["crop"]["crop"] == "rice"
    print("✅ test_get_crop_rice passed")


def test_get_crop_fuzzy():
    r = client.get("/crops/sugar")
    assert r.status_code == 200
    data = r.json()
    assert data["found"] is True
    print("✅ test_get_crop_fuzzy passed")


def test_get_crop_not_found():
    r = client.get("/crops/dragonfruit")
    assert r.status_code == 200
    data = r.json()
    assert data["found"] is False
    print("✅ test_get_crop_not_found passed")


def test_list_schemes():
    r = client.get("/schemes")
    assert r.status_code == 200
    schemes = r.json()
    assert len(schemes) > 0
    print(f"✅ test_list_schemes ({len(schemes)} schemes)")


def test_get_scheme():
    r = client.get("/schemes/PM-KISAN")
    assert r.status_code == 200
    data = r.json()
    assert "PM-KISAN" in data["name"]
    print("✅ test_get_scheme passed")


def test_search_schemes():
    r = client.get("/schemes/search?q=loan")
    assert r.status_code == 200
    data = r.json()
    assert len(data["results"]) > 0
    print(f"✅ test_search_schemes ({len(data['results'])} results)")


def test_scheme_not_found():
    r = client.get("/schemes/nonexistent")
    assert r.status_code == 404
    print("✅ test_scheme_not_found passed")


def test_weather():
    r = client.get("/weather/Delhi")
    assert r.status_code == 200
    data = r.json()
    assert data["location"] == "Delhi"
    print(f"✅ test_weather ({data.get('temperature', '?')}°C)")


def test_openapi_schema():
    r = client.get("/openapi.json")
    assert r.status_code == 200
    schema = r.json()
    assert "paths" in schema
    assert "/crops/{crop_name}" in schema["paths"]
    print("✅ test_openapi_schema passed")


if __name__ == "__main__":
    tests = [
        test_health, test_root, test_list_crops, test_get_crop_rice,
        test_get_crop_fuzzy, test_get_crop_not_found,
        test_list_schemes, test_get_scheme, test_search_schemes,
        test_scheme_not_found, test_weather, test_openapi_schema,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t(); passed += 1
        except Exception as e:
            print(f"❌ {t.__name__}: {e}"); failed += 1
    print(f"\n{'='*40}\n{passed} passed, {failed} failed")
    if not failed:
        print("All tests passed! 🎉")

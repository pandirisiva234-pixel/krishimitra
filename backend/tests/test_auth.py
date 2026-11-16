"""Authentication and user-management tests (Module 1)."""
from app.core.security import create_access_token
from tests.conftest import register


def test_register_returns_token_and_profile(client):
    data = register(client, email="Ravi@Example.com")
    assert data["token_type"] == "bearer"
    assert data["user"]["phone"] == "9876543210"
    assert data["user"]["email"] == "ravi@example.com"
    assert data["user"]["role"] == "farmer"
    assert data["user"]["preferred_language"]["code"] == "te"
    assert "password" not in str(data).lower().replace("password_hash", "")


def test_phone_is_normalised_from_plus91(client):
    data = register(client, phone="+91 98765 43210")
    assert data["user"]["phone"] == "9876543210"


def test_duplicate_phone_rejected(client):
    register(client)
    resp = client.post("/api/auth/register", json={"full_name": "X Y", "phone": "9876543210", "password": "Abcdef12"})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "conflict"


def test_weak_password_and_bad_phone_rejected(client):
    resp = client.post("/api/auth/register", json={"full_name": "X Y", "phone": "12345", "password": "short"})
    assert resp.status_code == 422
    fields = {d["field"] for d in resp.json()["error"]["details"]}
    assert {"phone", "password"} <= fields


def test_unknown_language_rejected(client):
    resp = client.post("/api/auth/register", json={"full_name": "X Y", "phone": "9876543211",
                                                   "password": "Abcdef12", "preferred_language": "xx"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "unsupported_language"


def test_login_with_phone_and_email(client):
    register(client, email="ravi@example.com")
    for username in ("9876543210", "ravi@example.com", "+919876543210"):
        resp = client.post("/api/auth/login", data={"username": username, "password": "Farmer123"})
        assert resp.status_code == 200, username
        assert resp.json()["user"]["last_login_at"] is not None


def test_wrong_password_gives_generic_error(client):
    register(client)
    bad_pw = client.post("/api/auth/login", data={"username": "9876543210", "password": "Wrong1234"})
    no_user = client.post("/api/auth/login", data={"username": "9123456789", "password": "Wrong1234"})
    assert bad_pw.status_code == no_user.status_code == 401
    assert bad_pw.json()["error"]["message"] == no_user.json()["error"]["message"]


def test_profile_requires_valid_token(client):
    assert client.get("/api/auth/profile").status_code == 401
    bad = client.get("/api/auth/profile", headers={"Authorization": "Bearer not-a-token"})
    assert bad.status_code == 401


def test_expired_token_rejected(client, farmer):
    expired = create_access_token(str(farmer["user"]["id"]), "farmer", expires_minutes=-1)
    resp = client.get("/api/auth/profile", headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "token_expired"


def test_get_and_update_profile(client, farmer):
    resp = client.put("/api/auth/profile", headers=farmer["headers"], json={
        "preferred_language": "hi", "latitude": 16.3, "longitude": 80.45, "primary_crops": "chilli,cotton",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["preferred_language"]["code"] == "hi"
    assert body["latitude"] == 16.3
    assert client.get("/api/auth/profile", headers=farmer["headers"]).json()["primary_crops"] == "chilli,cotton"


def test_change_password(client, farmer):
    wrong = client.post("/api/auth/change-password", headers=farmer["headers"],
                        json={"current_password": "nope12345", "new_password": "NewPass123"})
    assert wrong.status_code == 400
    ok = client.post("/api/auth/change-password", headers=farmer["headers"],
                     json={"current_password": "Farmer123", "new_password": "NewPass123"})
    assert ok.status_code == 200
    assert client.post("/api/auth/login", data={"username": "9876543210", "password": "NewPass123"}).status_code == 200


def test_disabled_user_cannot_login_or_use_token(client, farmer, admin):
    uid = farmer["user"]["id"]
    assert client.patch(f"/api/admin/users/{uid}", headers=admin["headers"], json={"is_active": False}).status_code == 200
    assert client.get("/api/auth/profile", headers=farmer["headers"]).status_code == 401
    assert client.post("/api/auth/login", data={"username": "9876543210", "password": "Farmer123"}).status_code == 401


def test_logout_and_languages(client, farmer):
    assert client.post("/api/auth/logout", headers=farmer["headers"]).status_code == 200
    codes = [lang["code"] for lang in client.get("/api/languages").json()]
    assert codes == ["te", "hi", "ta", "kn", "ml", "mr", "bn", "gu", "ur", "en"]

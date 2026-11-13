"""E2E tests: auth endpoints (Phase 4)."""


class TestLoginE2E:
    def test_first_login_creates_user_and_returns_stub_token(self, client):
        response = client.post("/api/auth/login", json={"username": "bob", "password": "pw"})
        assert response.status_code == 200
        body = response.json()
        assert body["access_token"] == "stub-token-for-bob"
        assert body["username"] == "bob"
        assert body["role"] == "user"

    def test_second_login_with_correct_password(self, client):
        client.post("/api/auth/login", json={"username": "carol", "password": "pw"})
        response = client.post("/api/auth/login", json={"username": "carol", "password": "pw"})
        assert response.status_code == 200
        assert response.json()["access_token"] == "stub-token-for-carol"

    def test_second_login_with_wrong_password_is_401(self, client):
        client.post("/api/auth/login", json={"username": "dave", "password": "pw"})
        response = client.post("/api/auth/login", json={"username": "dave", "password": "nope"})
        assert response.status_code == 401

    def test_seeded_admin_logs_in_with_seeded_password(self, client):
        # "admin" is seeded at startup with password "12345@mn"
        response = client.post("/api/auth/login", json={"username": "admin", "password": "12345@mn"})
        assert response.status_code == 200
        assert response.json()["role"] == "admin"

    def test_seeded_admin_wrong_password_is_401(self, client):
        response = client.post("/api/auth/login", json={"username": "admin", "password": "pw"})
        assert response.status_code == 401

    def test_missing_fields_are_422(self, client):
        assert client.post("/api/auth/login", json={"username": "x"}).status_code == 422
        assert client.post("/api/auth/login", json={}).status_code == 422


class TestAuthEnforcementE2E:
    def test_create_room_requires_auth(self, client):
        response = client.post("/api/rooms", json={"name": "standup"})
        assert response.status_code == 401

    def test_garbage_token_is_401(self, client):
        client.headers["Authorization"] = "Bearer not-a-real-token"
        response = client.post("/api/rooms", json={"name": "standup"})
        assert response.status_code == 401

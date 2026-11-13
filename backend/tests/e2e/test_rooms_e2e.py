"""E2E tests: rooms API (Phase 4) — the acceptance criteria for the backend."""

import jwt

JITSI_SECRET = "test-secret"


def _create_room(client, name="standup"):
    response = client.post("/api/rooms", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


class TestRoomLifecycleE2E:
    def test_create_room(self, auth_client):
        room = _create_room(auth_client, "  standup  ")
        assert room["id"] > 0
        assert room["name"] == "standup"  # trimmed
        assert room["jitsi_room_id"]
        assert room["is_active"] is True
        assert room["participant_count"] == 0

    def test_create_room_blank_name_is_422(self, auth_client):
        response = auth_client.post("/api/rooms", json={"name": "   "})
        assert response.status_code == 422

    def test_list_rooms_is_open_and_shows_counts(self, client, auth_client):
        created = _create_room(auth_client, "team")
        response = client.get("/api/rooms")  # no auth header
        assert response.status_code == 200
        items = response.json()["items"]
        assert any(r["id"] == created["id"] for r in items)

    def test_get_room_detail_with_participants(self, client, auth_client):
        created = _create_room(auth_client)
        auth_client.post(f"/api/rooms/{created['id']}/join")
        response = client.get(f"/api/rooms/{created['id']}")
        assert response.status_code == 200
        detail = response.json()
        assert detail["name"] == "standup"
        assert [p["username"] for p in detail["participants"]] == ["alice"]

    def test_get_missing_room_is_404(self, client):
        assert client.get("/api/rooms/9999").status_code == 404

    def test_end_room_hides_it_from_list(self, client, auth_client):
        created = _create_room(auth_client)
        assert auth_client.delete(f"/api/rooms/{created['id']}").status_code == 204
        items = client.get("/api/rooms").json()["items"]
        assert all(r["id"] != created["id"] for r in items)
        assert client.get(f"/api/rooms/{created['id']}").json()["is_active"] is False

    def test_end_missing_room_is_404(self, auth_client):
        assert auth_client.delete("/api/rooms/9999").status_code == 404


class TestParticipationE2E:
    def test_join_and_leave_cycle(self, client, auth_client):
        created = _create_room(auth_client)

        response = auth_client.post(f"/api/rooms/{created['id']}/join")
        assert response.status_code == 204
        assert auth_client.get(f"/api/rooms/{created['id']}/participants").json()[0]["username"] == "alice"

        assert auth_client.post(f"/api/rooms/{created['id']}/leave").status_code == 204
        assert auth_client.get(f"/api/rooms/{created['id']}/participants").json()[0]["left_at"] is not None
        items = client.get("/api/rooms").json()["items"]
        assert items[0]["participant_count"] == 0

    def test_join_missing_room_is_404(self, auth_client):
        assert auth_client.post("/api/rooms/9999/join").status_code == 404

    def test_join_requires_auth(self, client):
        assert client.post("/api/rooms/1/join").status_code == 401


class TestChatE2E:
    def test_send_and_list_messages(self, auth_client):
        created = _create_room(auth_client)
        sent = auth_client.post(
            f"/api/rooms/{created['id']}/messages", json={"message": "  hello  "}
        )
        assert sent.status_code == 201
        assert sent.json()["text"] == "hello"
        assert sent.json()["username"] == "alice"

        response = auth_client.get(f"/api/rooms/{created['id']}/messages")
        assert response.status_code == 200
        items = response.json()["items"]
        assert [m["text"] for m in items] == ["hello"]

    def test_blank_message_is_422(self, auth_client):
        created = _create_room(auth_client)
        response = auth_client.post(f"/api/rooms/{created['id']}/messages", json={"message": "  "})
        assert response.status_code == 422

    def test_send_to_missing_room_is_404(self, auth_client):
        response = auth_client.post("/api/rooms/9999/messages", json={"message": "hi"})
        assert response.status_code == 404

    def test_send_requires_auth(self, client):
        assert client.post("/api/rooms/1/messages", json={"message": "hi"}).status_code == 401


class TestTokenE2E:
    def test_token_is_valid_jitsi_jwt(self, auth_client):
        created = _create_room(auth_client)
        response = auth_client.post(f"/api/rooms/{created['id']}/token")
        assert response.status_code == 200

        decoded = jwt.decode(
            response.json()["token"], JITSI_SECRET, algorithms=["HS256"], audience="jitsi"
        )
        assert decoded["iss"] == "video-call-system"
        assert decoded["sub"] == "meet.jitsi"
        assert decoded["room"] == created["jitsi_room_id"]
        assert decoded["context"]["user"]["name"] == "alice"

    def test_token_for_missing_room_is_404(self, auth_client):
        assert auth_client.post("/api/rooms/9999/token").status_code == 404

    def test_token_for_ended_room_is_400(self, auth_client):
        created = _create_room(auth_client)
        auth_client.delete(f"/api/rooms/{created['id']}")
        assert auth_client.post(f"/api/rooms/{created['id']}/token").status_code == 400

    def test_token_requires_auth(self, client):
        assert client.post("/api/rooms/1/token").status_code == 401

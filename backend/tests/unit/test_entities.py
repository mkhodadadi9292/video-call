"""Unit tests for domain entities and value objects (Phase 1)."""

import pytest

from backend.domain.entities import (
    ChatMessage,
    JitsiConfig,
    JitsiRoomId,
    Participant,
    Room,
    RoomName,
)


class TestRoomName:
    def test_strips_surrounding_whitespace(self):
        assert RoomName("  standup  ").value == "standup"

    def test_accepts_min_length_after_strip(self):
        assert RoomName("a").value == "a"

    def test_rejects_empty(self):
        with pytest.raises(ValueError):
            RoomName("")

    def test_rejects_whitespace_only(self):
        with pytest.raises(ValueError):
            RoomName("   ")

    def test_rejects_longer_than_200(self):
        with pytest.raises(ValueError):
            RoomName("x" * 201)

    def test_accepts_exactly_200(self):
        assert RoomName("x" * 200).value == "x" * 200


class TestJitsiRoomId:
    def test_generate_returns_urlsafe_value(self):
        jitsi_id = JitsiRoomId.generate()
        assert len(jitsi_id.value) >= 16
        assert "/" not in jitsi_id.value
        assert "+" not in jitsi_id.value

    def test_generate_produces_distinct_ids(self):
        ids = {JitsiRoomId.generate().value for _ in range(50)}
        assert len(ids) == 50


class TestRoom:
    def test_new_room_is_active_by_default(self):
        room = Room(id=None, name=RoomName("demo"), jitsi_room_id=JitsiRoomId("abc123"), created_by=1)
        assert room.is_active is True

    def test_close_returns_inactive_copy(self):
        room = Room(id=1, name=RoomName("demo"), jitsi_room_id=JitsiRoomId("abc123"), created_by=1)
        closed = room.close()
        assert closed.is_active is False
        assert room.is_active is True  # original untouched (immutability)


class TestChatMessage:
    def test_strips_text(self):
        msg = ChatMessage(id=None, room_id=1, user_id=2, username="bob", text="  hi  ")
        assert msg.text == "hi"

    def test_rejects_empty_text(self):
        with pytest.raises(ValueError):
            ChatMessage(id=None, room_id=1, user_id=2, username="bob", text="")


class TestParticipant:
    def test_connected_while_left_at_is_none(self):
        assert Participant(user_id=1, username="bob").is_connected is True

    def test_not_connected_after_leaving(self):
        from datetime import datetime, timezone
        p = Participant(user_id=1, username="bob", left_at=datetime.now(timezone.utc))
        assert p.is_connected is False


class TestJitsiConfig:
    def test_holds_app_credentials(self):
        cfg = JitsiConfig(app_id="video-call-system", app_secret="s3cret")
        assert cfg.app_id == "video-call-system"
        assert cfg.app_secret == "s3cret"

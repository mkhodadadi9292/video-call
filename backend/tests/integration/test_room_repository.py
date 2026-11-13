"""Integration tests: SqlAlchemyRoomRepository against real (in-memory) SQLite."""

import pytest

from backend.domain.entities import ChatMessage, JitsiRoomId, Room, RoomName
from backend.infrastructure.db.models import User
from backend.infrastructure.db.room_repository import SqlAlchemyRoomRepository


@pytest.fixture
def repo(db_session):
    return SqlAlchemyRoomRepository(db_session)


@pytest.fixture
def users(db_session):
    alice = User(username="alice", password_hash="x", role="user")
    bob = User(username="bob", password_hash="x", role="user")
    db_session.add_all([alice, bob])
    db_session.commit()
    return {"alice": alice.id, "bob": bob.id}


def _room(created_by: int, name: str = "standup") -> Room:
    return Room(id=None, name=RoomName(name), jitsi_room_id=JitsiRoomId.generate(), created_by=created_by)


class TestRooms:
    def test_create_assigns_id_and_timestamp(self, repo, users):
        created = repo.create_room(_room(users["alice"]))
        assert created.id is not None
        assert created.created_at is not None
        assert created.name.value == "standup"

    def test_list_active_rooms_newest_first_excludes_closed(self, repo, users):
        first = repo.create_room(_room(users["alice"], "first"))
        second = repo.create_room(_room(users["alice"], "second"))
        repo.close_room(first.id)

        rooms = repo.list_active_rooms()
        assert [r.name.value for r in rooms] == ["second"]

    def test_get_room_returns_none_when_missing(self, repo):
        assert repo.get_room(999) is None

    def test_close_room_returns_none_when_missing(self, repo):
        assert repo.close_room(999) is None

    def test_close_room_persists_inactive(self, repo, users):
        room = repo.create_room(_room(users["alice"]))
        closed = repo.close_room(room.id)
        assert closed.is_active is False
        assert repo.get_room(room.id).is_active is False


class TestParticipants:
    def test_join_leave_rejoin_cycle(self, repo, users):
        room = repo.create_room(_room(users["alice"]))

        repo.add_participant(room.id, users["bob"])
        assert repo.count_participants(room.id) == 1

        repo.remove_participant(room.id, users["bob"])
        assert repo.count_participants(room.id) == 0

        repo.add_participant(room.id, users["bob"])  # rejoin
        assert repo.count_participants(room.id) == 1

    def test_remove_is_idempotent(self, repo, users):
        room = repo.create_room(_room(users["alice"]))
        repo.remove_participant(room.id, users["bob"])  # never joined — no error

    def test_list_participants_includes_usernames(self, repo, users):
        room = repo.create_room(_room(users["alice"]))
        repo.add_participant(room.id, users["alice"])
        repo.add_participant(room.id, users["bob"])

        participants = repo.list_participants(room.id)
        assert [(p.user_id, p.username) for p in participants] == [
            (users["alice"], "alice"),
            (users["bob"], "bob"),
        ]
        assert all(p.is_connected for p in participants)

    def test_left_participant_is_listed_with_left_at(self, repo, users):
        room = repo.create_room(_room(users["alice"]))
        repo.add_participant(room.id, users["bob"])
        repo.remove_participant(room.id, users["bob"])

        participants = repo.list_participants(room.id)
        assert len(participants) == 1
        assert participants[0].left_at is not None


class TestMessages:
    def test_add_message_returns_username(self, repo, users):
        room = repo.create_room(_room(users["alice"]))
        msg = repo.add_message(room.id, users["bob"], "hello")
        assert msg.username == "bob"
        assert msg.text == "hello"
        assert msg.id is not None

    def test_add_message_rejects_blank_text(self, repo, users):
        room = repo.create_room(_room(users["alice"]))
        with pytest.raises(ValueError):
            repo.add_message(room.id, users["bob"], "   ")

    def test_list_messages_oldest_first_with_pagination(self, repo, users):
        room = repo.create_room(_room(users["alice"]))
        for i in range(5):
            repo.add_message(room.id, users["alice"], f"msg{i}")

        # Pages count from the newest message; each page is oldest-first.
        page1 = repo.list_messages(room.id, page=1, size=2)
        page3 = repo.list_messages(room.id, page=3, size=2)
        assert [m.text for m in page1] == ["msg3", "msg4"]
        assert [m.text for m in page3] == ["msg0"]

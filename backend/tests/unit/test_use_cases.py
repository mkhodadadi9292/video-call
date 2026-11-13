"""Unit tests for application use cases (Phase 2) — run against fakes."""

import pytest

from backend.application.errors import (
    JitsiConfigMissingError,
    RoomInactiveError,
    RoomNotFoundError,
)
from backend.application.use_cases.chat import ListMessagesUseCase, SendMessageUseCase
from backend.application.use_cases.participation import (
    JoinRoomUseCase,
    LeaveRoomUseCase,
    ListParticipantsUseCase,
)
from backend.application.use_cases.room_lifecycle import (
    CreateRoomUseCase,
    EndRoomUseCase,
    GetRoomUseCase,
    ListRoomsUseCase,
)
from backend.application.use_cases.token import GenerateJoinTokenUseCase
from backend.domain.entities import JitsiConfig
from backend.tests.fakes import (
    FakeTokenGenerator,
    InMemoryRoomRepository,
    StaticJitsiConfigProvider,
)


@pytest.fixture
def repo():
    r = InMemoryRoomRepository()
    r.add_user(1, "alice")
    r.add_user(2, "bob")
    return r


@pytest.fixture
def created_room(repo):
    return CreateRoomUseCase(repo).execute("Standup", user_id=1)


class TestCreateRoomUseCase:
    def test_creates_room_with_generated_jitsi_id(self, repo):
        dto = CreateRoomUseCase(repo).execute("  Standup  ", user_id=1)
        assert dto.name == "Standup"  # trimmed by RoomName
        assert dto.jitsi_room_id
        assert dto.created_by == 1
        assert dto.is_active is True
        assert dto.id is not None

    def test_rejects_invalid_name(self, repo):
        with pytest.raises(ValueError):
            CreateRoomUseCase(repo).execute("   ", user_id=1)


class TestListRoomsUseCase:
    def test_lists_only_active_rooms_with_participant_counts(self, repo):
        a = CreateRoomUseCase(repo).execute("A", 1)
        b = CreateRoomUseCase(repo).execute("B", 1)
        JoinRoomUseCase(repo).execute(a.id, 2)
        JoinRoomUseCase(repo).execute(a.id, 1)
        EndRoomUseCase(repo).execute(b.id)

        rooms = ListRoomsUseCase(repo).execute()
        assert [r.name for r in rooms] == ["A"]
        assert rooms[0].participant_count == 2


class TestGetRoomUseCase:
    def test_returns_detail_with_participants(self, repo, created_room):
        JoinRoomUseCase(repo).execute(created_room.id, 2)
        detail = GetRoomUseCase(repo).execute(created_room.id)
        assert detail.name == "Standup"
        assert [p.username for p in detail.participants] == ["bob"]

    def test_raises_when_missing(self, repo):
        with pytest.raises(RoomNotFoundError):
            GetRoomUseCase(repo).execute(999)


class TestEndRoomUseCase:
    def test_closes_room(self, repo, created_room):
        EndRoomUseCase(repo).execute(created_room.id)
        assert repo.get_room(created_room.id).is_active is False

    def test_raises_when_missing(self, repo):
        with pytest.raises(RoomNotFoundError):
            EndRoomUseCase(repo).execute(999)


class TestJoinLeaveUseCases:
    def test_join_and_leave_cycle(self, repo, created_room):
        JoinRoomUseCase(repo).execute(created_room.id, 2)
        assert repo.count_participants(created_room.id) == 1

        LeaveRoomUseCase(repo).execute(created_room.id, 2)
        assert repo.count_participants(created_room.id) == 0

    def test_rejoin_restores_connection(self, repo, created_room):
        JoinRoomUseCase(repo).execute(created_room.id, 2)
        LeaveRoomUseCase(repo).execute(created_room.id, 2)
        JoinRoomUseCase(repo).execute(created_room.id, 2)
        assert repo.count_participants(created_room.id) == 1

    def test_join_missing_room_raises(self, repo):
        with pytest.raises(RoomNotFoundError):
            JoinRoomUseCase(repo).execute(999, 2)

    def test_leave_is_idempotent(self, repo, created_room):
        LeaveRoomUseCase(repo).execute(created_room.id, 2)  # never joined
        LeaveRoomUseCase(repo).execute(created_room.id, 2)


class TestListParticipantsUseCase:
    def test_lists_participants(self, repo, created_room):
        JoinRoomUseCase(repo).execute(created_room.id, 1)
        JoinRoomUseCase(repo).execute(created_room.id, 2)
        participants = ListParticipantsUseCase(repo).execute(created_room.id)
        assert [p.username for p in participants] == ["alice", "bob"]

    def test_raises_when_room_missing(self, repo):
        with pytest.raises(RoomNotFoundError):
            ListParticipantsUseCase(repo).execute(999)


class TestChatUseCases:
    def test_send_and_list_messages(self, repo, created_room):
        SendMessageUseCase(repo).execute(created_room.id, 1, "  hello  ")
        SendMessageUseCase(repo).execute(created_room.id, 2, "hi")

        messages = ListMessagesUseCase(repo).execute(created_room.id)
        assert [(m.username, m.text) for m in messages] == [("alice", "hello"), ("bob", "hi")]

    def test_send_rejects_blank_text(self, repo, created_room):
        with pytest.raises(ValueError):
            SendMessageUseCase(repo).execute(created_room.id, 1, "   ")

    def test_send_to_missing_room_raises(self, repo):
        with pytest.raises(RoomNotFoundError):
            SendMessageUseCase(repo).execute(999, 1, "hi")

    def test_list_messages_paginates(self, repo, created_room):
        for i in range(5):
            SendMessageUseCase(repo).execute(created_room.id, 1, f"msg{i}")
        page2 = ListMessagesUseCase(repo).execute(created_room.id, page=2, size=2)
        assert [m.text for m in page2] == ["msg1", "msg2"]

    def test_list_messages_missing_room_raises(self, repo):
        with pytest.raises(RoomNotFoundError):
            ListMessagesUseCase(repo).execute(999)


class TestGenerateJoinTokenUseCase:
    @pytest.fixture
    def token_generator(self):
        return FakeTokenGenerator()

    @pytest.fixture
    def config(self):
        return StaticJitsiConfigProvider(JitsiConfig(app_id="vcs", app_secret="s3cret"))

    def test_generates_token_for_active_room(self, repo, created_room, token_generator, config):
        dto = GenerateJoinTokenUseCase(repo, token_generator, config).execute(
            created_room.id, username="alice"
        )
        assert dto.token.startswith("fake-jwt.")
        assert token_generator.calls == [(created_room.jitsi_room_id, "alice")]

    def test_raises_when_room_missing(self, repo, token_generator, config):
        with pytest.raises(RoomNotFoundError):
            GenerateJoinTokenUseCase(repo, token_generator, config).execute(999, "alice")

    def test_raises_when_room_inactive(self, repo, created_room, token_generator, config):
        EndRoomUseCase(repo).execute(created_room.id)
        with pytest.raises(RoomInactiveError):
            GenerateJoinTokenUseCase(repo, token_generator, config).execute(
                created_room.id, "alice"
            )

    def test_raises_when_config_missing(self, repo, created_room, token_generator):
        use_case = GenerateJoinTokenUseCase(repo, token_generator, StaticJitsiConfigProvider(None))
        with pytest.raises(JitsiConfigMissingError):
            use_case.execute(created_room.id, "alice")

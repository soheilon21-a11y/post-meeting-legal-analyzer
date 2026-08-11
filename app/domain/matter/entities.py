from __future__ import annotations

from typing import TYPE_CHECKING

from app.domain.exceptions.lifecycle import InvalidStateTransition
from app.domain.matter.enums import MatterClassification
from app.domain.matter.enums import MatterMemberRole
from app.domain.matter.enums import MatterStatus
from app.domain.matter.rules import ensure_matter_is_modifiable
from app.domain.matter.rules import ensure_owner_remains
from app.domain.shared.aggregate_root import AggregateRoot
from app.domain.shared.entity import Entity
from app.domain.shared.identifiers import MatterId
from app.domain.shared.identifiers import UserId

if TYPE_CHECKING:
    from app.domain.matter.value_objects import MatterName
    from app.domain.matter.value_objects import MatterNumber


class MatterMember(Entity[UserId]):
    def __init__(self, user_id: UserId, role: MatterMemberRole) -> None:
        super().__init__(user_id)
        self._role = role

    @property
    def user_id(self) -> UserId:
        return self.id

    @property
    def role(self) -> MatterMemberRole:
        return self._role

    def change_role(self, role: MatterMemberRole) -> None:
        self._role = role


class Matter(AggregateRoot[MatterId]):
    def __init__(
        self,
        name: MatterName,
        classification: MatterClassification = MatterClassification.GENERAL,
        matter_number: MatterNumber | None = None,
        matter_id: MatterId | None = None,
    ) -> None:
        super().__init__(matter_id)
        self._name = name
        self._classification = classification
        self._matter_number = matter_number
        self._status = MatterStatus.ACTIVE
        self._legal_hold = False
        self._members: dict[UserId, MatterMember] = {}

    @property
    def name(self) -> MatterName:
        return self._name

    @property
    def classification(self) -> MatterClassification:
        return self._classification

    @property
    def matter_number(self) -> MatterNumber | None:
        return self._matter_number

    @property
    def status(self) -> MatterStatus:
        return self._status

    @property
    def legal_hold(self) -> bool:
        return self._legal_hold

    @property
    def members(self) -> tuple[MatterMember, ...]:
        return tuple(self._members.values())

    def rename(self, name: MatterName) -> None:
        ensure_matter_is_modifiable(self._status, self._legal_hold)
        self._name = name

    def add_member(self, user_id: UserId, role: MatterMemberRole) -> MatterMember:
        ensure_matter_is_modifiable(self._status, self._legal_hold)
        if user_id in self._members:
            raise ValueError("User is already a member of this matter")
        member = MatterMember(user_id, role)
        self._members[user_id] = member
        return member

    def change_member_role(self, user_id: UserId, role: MatterMemberRole) -> None:
        ensure_matter_is_modifiable(self._status, self._legal_hold)
        member = self._members.get(user_id)
        if member is None:
            raise KeyError("User is not a member of this matter")
        if member.role is MatterMemberRole.OWNER and role is not MatterMemberRole.OWNER:
            ensure_owner_remains(self._owner_count(), True)
        member.change_role(role)

    def remove_member(self, user_id: UserId) -> None:
        ensure_matter_is_modifiable(self._status, self._legal_hold)
        member = self._members.get(user_id)
        if member is None:
            raise KeyError("User is not a member of this matter")
        ensure_owner_remains(self._owner_count(), member.role is MatterMemberRole.OWNER)
        del self._members[user_id]

    def apply_legal_hold(self) -> None:
        self._legal_hold = True

    def release_legal_hold(self) -> None:
        self._legal_hold = False

    def put_on_hold(self) -> None:
        if self._status is not MatterStatus.ACTIVE:
            raise InvalidStateTransition("Matter", self._status, MatterStatus.ON_HOLD)
        self._status = MatterStatus.ON_HOLD

    def resume(self) -> None:
        if self._status is not MatterStatus.ON_HOLD:
            raise InvalidStateTransition("Matter", self._status, MatterStatus.ACTIVE)
        self._status = MatterStatus.ACTIVE

    def close(self) -> None:
        if self._status not in (MatterStatus.ACTIVE, MatterStatus.ON_HOLD):
            raise InvalidStateTransition("Matter", self._status, MatterStatus.CLOSED)
        self._status = MatterStatus.CLOSED

    def archive(self) -> None:
        if self._status is not MatterStatus.CLOSED:
            raise InvalidStateTransition("Matter", self._status, MatterStatus.ARCHIVED)
        self._status = MatterStatus.ARCHIVED

    def _owner_count(self) -> int:
        return sum(member.role is MatterMemberRole.OWNER for member in self._members.values())

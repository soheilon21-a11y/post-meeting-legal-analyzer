from app.domain.exceptions.lifecycle import InvalidStateTransition
from app.domain.matter.enums import MatterStatus


def ensure_matter_is_modifiable(status: MatterStatus, legal_hold: bool) -> None:
    if status in (MatterStatus.CLOSED, MatterStatus.ARCHIVED):
        raise InvalidStateTransition("Matter", status, MatterStatus.ACTIVE)
    if legal_hold:
        raise ValueError("A matter under legal hold cannot be structurally modified")


def ensure_owner_remains(members: int, removing_owner: bool) -> None:
    if removing_owner and members <= 1:
        raise ValueError("A matter must retain at least one owner")

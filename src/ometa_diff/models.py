"""Pydantic models for ometa-diff data structures."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ChangeType(str, Enum):
    """Type of change observed in a diff."""

    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"


class ChangeSeverity(str, Enum):
    """Impact severity of a metadata change.

    MAJOR: Breaking — column removed, dataType changed, owner removed.
    MINOR: Informational — description edited, tag added/removed.
    PATCH: Cosmetic — displayName changed, href updated.
    """

    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"


class FieldChange(BaseModel):
    """A single field-level change between two entity versions."""

    field_path: str
    """Dot-notation path to the changed field, e.g. 'columns.payment_id.description'."""
    change_type: ChangeType
    severity: ChangeSeverity
    old_value: object | None = None
    new_value: object | None = None


class EntityDiff(BaseModel):
    """Diff result between two versions of a single metadata entity."""

    entity_type: str
    """OM entity type string, e.g. 'table', 'dashboard'."""
    entity_fqn: str
    """Fully qualified name, e.g. 'my_service.db.schema.payments'."""
    entity_id: str
    from_version: float
    to_version: float
    updated_by: str
    updated_at: datetime
    changes: list[FieldChange] = Field(default_factory=list)
    is_major: bool
    """True if any change has MAJOR severity."""
    summary: str
    """Human-readable summary, e.g. '3 changes: 1 column removed, description updated'."""


class CatalogChangelog(BaseModel):
    """Aggregated changelog across multiple entities over a time window."""

    scope: str
    """Scope descriptor, e.g. 'service:my_service', 'type:table', 'user:admin'."""
    from_date: datetime
    to_date: datetime
    total_entities_changed: int
    total_changes: int
    major_changes: int
    minor_changes: int
    entries: list[EntityDiff] = Field(default_factory=list)
    top_changers: list[dict] = Field(default_factory=list)
    """Sorted list of most active users, e.g. [{'user': 'admin', 'change_count': 12}]."""

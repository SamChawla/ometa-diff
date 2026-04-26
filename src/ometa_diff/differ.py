"""Core diff engine: compares two JSON version snapshots of OM entities."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, cast

from ometa_diff.client import OMVersionClient
from ometa_diff.exceptions import NoDiffAvailable
from ometa_diff.models import ChangeSeverity, ChangeType, EntityDiff, FieldChange

# Fields that carry no semantic meaning and change on every save.
NOISE_FIELDS: frozenset[str] = frozenset(
    {
        "version",
        "updatedAt",
        "updatedBy",
        "changeDescription",
        "href",
        "incrementalChangeDescription",
    }
)

_EMPTY_FROZENSET: frozenset[str] = frozenset()

# Fields to treat as a single atomic value rather than recursing into sub-fields.
ATOMIC_FIELDS: frozenset[str] = frozenset(
    {
        "owner",
        "service",
        "database",
        "databaseSchema",
        "domain",
        "extension",
        "retentionPeriod",
    }
)

# Array fields and the key used to match items across versions.
KEYED_ARRAYS: dict[str, str] = {
    "columns": "name",
    "tags": "tagFQN",
    "followers": "id",
    "tableConstraints": "constraintType",
    "customMetrics": "name",
}

# Fields inside a column object that are derived / not meaningful to diff.
COLUMN_NOISE_FIELDS: frozenset[str] = frozenset(
    {
        "fullyQualifiedName",
        "href",
        "ordinalPosition",
    }
)


# ---------------------------------------------------------------------------
# Severity classification
# ---------------------------------------------------------------------------


def _classify_severity(field_path: str, change_type: ChangeType) -> ChangeSeverity:
    """Return the severity of a change at the given dot-notation path.

    Args:
        field_path: Dot-notation path to the field, e.g. 'columns.payment_id.dataType'.
        change_type: Whether the field was added, removed, or modified.
    """
    parts = field_path.split(".")
    top = parts[0]

    if top == "columns":
        if len(parts) == 2:
            # Whole column added or removed.
            if change_type == ChangeType.REMOVED:
                return ChangeSeverity.MAJOR
            return ChangeSeverity.MINOR
        if len(parts) >= 3 and parts[2] == "dataType":
            return ChangeSeverity.MAJOR
        return ChangeSeverity.MINOR

    if top == "tags":
        return ChangeSeverity.MINOR

    if top == "owner":
        return ChangeSeverity.MAJOR if change_type == ChangeType.REMOVED else ChangeSeverity.MINOR

    if top in ("description", "tableConstraints", "tableType", "schema"):
        return ChangeSeverity.MINOR

    return ChangeSeverity.PATCH


# ---------------------------------------------------------------------------
# Recursive comparison helpers
# ---------------------------------------------------------------------------


def _compare_keyed_arrays(
    old_list: list[dict[str, Any]],
    new_list: list[dict[str, Any]],
    path: str,
    id_key: str,
    extra_noise: frozenset[str] = _EMPTY_FROZENSET,
) -> list[FieldChange]:
    """Compare two arrays whose items are matched by a stable identity key.

    Args:
        old_list: Items in the old version.
        new_list: Items in the new version.
        path: Dot-notation path to the array field (e.g. 'columns').
        id_key: Field name used to match items (e.g. 'name' for columns).
        extra_noise: Additional field names to ignore within each item.
    """
    old_by_key = {item[id_key]: item for item in old_list if id_key in item}
    new_by_key = {item[id_key]: item for item in new_list if id_key in item}
    all_keys = sorted(set(old_by_key) | set(new_by_key))
    changes: list[FieldChange] = []

    for k in all_keys:
        item_path = f"{path}.{k}"
        in_old = k in old_by_key
        in_new = k in new_by_key

        if not in_old:
            severity = _classify_severity(item_path, ChangeType.ADDED)
            changes.append(
                FieldChange(
                    field_path=item_path,
                    change_type=ChangeType.ADDED,
                    severity=severity,
                    old_value=None,
                    new_value=new_by_key[k],
                )
            )
        elif not in_new:
            severity = _classify_severity(item_path, ChangeType.REMOVED)
            changes.append(
                FieldChange(
                    field_path=item_path,
                    change_type=ChangeType.REMOVED,
                    severity=severity,
                    old_value=old_by_key[k],
                    new_value=None,
                )
            )
        elif old_by_key[k] != new_by_key[k]:
            # Item exists in both but has changed — recurse to find specific sub-changes.
            changes.extend(_compare_dicts(old_by_key[k], new_by_key[k], item_path, extra_noise))

    return changes


def _compare_dicts(
    old: dict[str, Any],
    new: dict[str, Any],
    path: str = "",
    extra_noise: frozenset[str] = _EMPTY_FROZENSET,
) -> list[FieldChange]:
    """Recursively compare two dicts and return a flat list of FieldChange objects.

    Args:
        old: Dict from the earlier version snapshot.
        new: Dict from the later version snapshot.
        path: Current dot-notation path prefix (empty at top level).
        extra_noise: Additional keys to skip at this level.
    """
    skip = NOISE_FIELDS | extra_noise
    all_keys = sorted((set(old.keys()) | set(new.keys())) - skip)
    changes: list[FieldChange] = []

    for key in all_keys:
        field_path = f"{path}.{key}" if path else key
        in_old = key in old
        in_new = key in new
        old_val: Any = old.get(key)
        new_val: Any = new.get(key)

        if not in_old:
            severity = _classify_severity(field_path, ChangeType.ADDED)
            changes.append(
                FieldChange(
                    field_path=field_path,
                    change_type=ChangeType.ADDED,
                    severity=severity,
                    old_value=None,
                    new_value=new_val,
                )
            )
            continue

        if not in_new:
            severity = _classify_severity(field_path, ChangeType.REMOVED)
            changes.append(
                FieldChange(
                    field_path=field_path,
                    change_type=ChangeType.REMOVED,
                    severity=severity,
                    old_value=old_val,
                    new_value=None,
                )
            )
            continue

        if old_val == new_val:
            continue

        # Values differ — determine how to compare.
        if old_val is None or new_val is None:
            # One side is explicitly null.
            ct = ChangeType.ADDED if old_val is None else ChangeType.REMOVED
            severity = _classify_severity(field_path, ct)
            changes.append(
                FieldChange(
                    field_path=field_path,
                    change_type=ct,
                    severity=severity,
                    old_value=old_val,
                    new_value=new_val,
                )
            )
        elif key in KEYED_ARRAYS and isinstance(old_val, list) and isinstance(new_val, list):
            col_noise: frozenset[str] = (
                COLUMN_NOISE_FIELDS if key == "columns" else _EMPTY_FROZENSET
            )
            changes.extend(
                _compare_keyed_arrays(
                    cast(list[dict[str, Any]], old_val),
                    cast(list[dict[str, Any]], new_val),
                    field_path,
                    KEYED_ARRAYS[key],
                    col_noise,
                )
            )
        elif key in ATOMIC_FIELDS or not isinstance(old_val, (dict, list)):
            severity = _classify_severity(field_path, ChangeType.MODIFIED)
            changes.append(
                FieldChange(
                    field_path=field_path,
                    change_type=ChangeType.MODIFIED,
                    severity=severity,
                    old_value=old_val,
                    new_value=new_val,
                )
            )
        elif isinstance(old_val, dict) and isinstance(new_val, dict):
            changes.extend(
                _compare_dicts(
                    cast(dict[str, Any], old_val), cast(dict[str, Any], new_val), field_path
                )
            )
        else:
            # Non-keyed list or mixed types — compare as atomic.
            severity = _classify_severity(field_path, ChangeType.MODIFIED)
            changes.append(
                FieldChange(
                    field_path=field_path,
                    change_type=ChangeType.MODIFIED,
                    severity=severity,
                    old_value=cast(object, old_val),
                    new_value=cast(object, new_val),
                )
            )

    return changes


# ---------------------------------------------------------------------------
# Summary generation
# ---------------------------------------------------------------------------


def _build_summary(changes: list[FieldChange]) -> str:
    """Generate a concise human-readable summary of a change list."""
    if not changes:
        return "No changes"

    n = len(changes)
    major = sum(1 for c in changes if c.severity == ChangeSeverity.MAJOR)
    minor = sum(1 for c in changes if c.severity == ChangeSeverity.MINOR)
    patch = n - major - minor

    parts: list[str] = []
    if major:
        parts.append(f"{major} major")
    if minor:
        parts.append(f"{minor} minor")
    if patch:
        parts.append(f"{patch} patch")

    return f"{n} change{'s' if n != 1 else ''}: {', '.join(parts)}"


# ---------------------------------------------------------------------------
# Public differ class
# ---------------------------------------------------------------------------


class MetadataDiffer:
    """Computes structured diffs between OpenMetadata entity version snapshots."""

    def __init__(self, client: OMVersionClient) -> None:
        """Initialise the differ with an OM API client.

        Args:
            client: Connected OMVersionClient used to fetch version snapshots.
        """
        self._client = client

    def diff_versions(
        self, old: dict[str, Any], new: dict[str, Any], entity_type: str
    ) -> EntityDiff:
        """Compare two raw version snapshot dicts and return a structured diff.

        Args:
            old: Entity JSON at the earlier version.
            new: Entity JSON at the later version.
            entity_type: OM entity type string, e.g. 'table'.

        Returns:
            EntityDiff with all detected FieldChange entries.
        """
        changes = _compare_dicts(old, new)
        is_major = any(c.severity == ChangeSeverity.MAJOR for c in changes)
        summary = _build_summary(changes)

        updated_at_ms = new.get("updatedAt") or old.get("updatedAt") or 0
        updated_at = datetime.fromtimestamp(updated_at_ms / 1000, tz=timezone.utc)

        return EntityDiff(
            entity_type=entity_type,
            entity_fqn=new.get("fullyQualifiedName", ""),
            entity_id=new.get("id", ""),
            from_version=float(old.get("version", 0)),
            to_version=float(new.get("version", 0)),
            updated_by=new.get("updatedBy", ""),
            updated_at=updated_at,
            changes=changes,
            is_major=is_major,
            summary=summary,
        )

    def diff_entity(
        self,
        entity_type: str,
        fqn: str,
        from_version: str | None = None,
        to_version: str | None = None,
    ) -> EntityDiff:
        """Fetch two versions from OM and diff them.

        Args:
            entity_type: OM entity type, e.g. 'table'.
            fqn: Fully qualified name of the entity.
            from_version: Earlier version string. Defaults to second-to-latest.
            to_version: Later version string. Defaults to latest.

        Returns:
            EntityDiff describing all changes between the two versions.

        Raises:
            NoDiffAvailable: If the entity has fewer than two versions.
        """
        entity = self._client.resolve_fqn(entity_type, fqn)
        entity_id = entity["id"]

        versions = self._client.list_versions(entity_type, entity_id)
        if len(versions) < 2:
            raise NoDiffAvailable(f"Entity '{fqn}' has only one version — nothing to diff.")

        if to_version is None:
            to_version = str(versions[-1])
        elif to_version not in versions:
            raise NoDiffAvailable(f"Version '{to_version}' not found for '{fqn}'.")

        if from_version is None:
            idx = versions.index(to_version)
            if idx == 0:
                raise NoDiffAvailable(
                    f"Version '{to_version}' is the first version of '{fqn}'"
                    " — nothing to diff against."
                )
            from_version = str(versions[idx - 1])
        elif from_version not in versions:
            raise NoDiffAvailable(f"Version '{from_version}' not found for '{fqn}'.")

        old_snap = self._client.get_version(entity_type, entity_id, from_version)
        new_snap = self._client.get_version(entity_type, entity_id, to_version)
        return self.diff_versions(old_snap, new_snap, entity_type)

    def diff_entity_since(
        self,
        entity_type: str,
        fqn: str,
        since_days: int = 7,
    ) -> list[EntityDiff]:
        """Return all consecutive version diffs within a time window.

        Args:
            entity_type: OM entity type, e.g. 'table'.
            fqn: Fully qualified name of the entity.
            since_days: How many days back to scan for version changes.

        Returns:
            List of EntityDiff objects, one per version transition in the window.
        """
        entity = self._client.resolve_fqn(entity_type, fqn)
        entity_id = entity["id"]
        versions = self._client.list_versions(entity_type, entity_id)

        if len(versions) < 2:
            return []

        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=since_days)
        diffs: list[EntityDiff] = []

        for i in range(1, len(versions)):
            new_snap = self._client.get_version(entity_type, entity_id, str(versions[i]))
            updated_at_ms = new_snap.get("updatedAt", 0)
            updated_at = datetime.fromtimestamp(updated_at_ms / 1000, tz=timezone.utc)
            if updated_at < cutoff:
                continue
            old_snap = self._client.get_version(entity_type, entity_id, str(versions[i - 1]))
            diffs.append(self.diff_versions(old_snap, new_snap, entity_type))

        return diffs

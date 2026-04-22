"""Multi-entity changelog aggregation over time windows."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

from ometa_diff.client import OMVersionClient
from ometa_diff.differ import MetadataDiffer
from ometa_diff.exceptions import NoDiffAvailable, OMNotFoundError
from ometa_diff.models import CatalogChangelog, ChangeSeverity, EntityDiff


def _aggregate(
    scope: str,
    from_date: datetime,
    to_date: datetime,
    all_diffs: list[EntityDiff],
) -> CatalogChangelog:
    """Build a CatalogChangelog from a flat list of EntityDiff objects."""
    changer_counts: Counter[str] = Counter(d.updated_by for d in all_diffs if d.updated_by)
    top_changers = [
        {"user": user, "change_count": count} for user, count in changer_counts.most_common(10)
    ]

    total_changes = sum(len(d.changes) for d in all_diffs)
    major_changes = sum(
        sum(1 for c in d.changes if c.severity == ChangeSeverity.MAJOR) for d in all_diffs
    )
    minor_changes = sum(
        sum(1 for c in d.changes if c.severity == ChangeSeverity.MINOR) for d in all_diffs
    )

    return CatalogChangelog(
        scope=scope,
        from_date=from_date,
        to_date=to_date,
        total_entities_changed=len(all_diffs),
        total_changes=total_changes,
        major_changes=major_changes,
        minor_changes=minor_changes,
        entries=all_diffs,
        top_changers=top_changers,
    )


def _diffs_for_entities(
    entities: list[dict],
    differ: MetadataDiffer,
    since_days: int,
    user_filter: str | None = None,
) -> list[EntityDiff]:
    """Fetch consecutive version diffs for a list of entity dicts.

    Args:
        entities: Search result dicts, each with entityType and fullyQualifiedName.
        differ: Differ instance used to fetch and compare versions.
        since_days: Time window in days.
        user_filter: If set, only include diffs where updated_by matches.
    """
    results: list[EntityDiff] = []
    for entity in entities:
        entity_type = entity.get("entityType") or entity.get("type", "")
        fqn = entity.get("fullyQualifiedName") or entity.get("name", "")
        if not entity_type or not fqn:
            continue
        try:
            diffs = differ.diff_entity_since(entity_type, fqn, since_days=since_days)
        except (NoDiffAvailable, OMNotFoundError, KeyError):
            continue
        if user_filter:
            diffs = [d for d in diffs if d.updated_by == user_filter]
        results.extend(diffs)
    return results


class ChangelogBuilder:
    """Aggregates entity-level diffs into a catalog-wide changelog."""

    def __init__(self, client: OMVersionClient) -> None:
        """Initialise with an OM API client.

        Args:
            client: Connected OMVersionClient used to discover and fetch entities.
        """
        self._client = client
        self._differ = MetadataDiffer(client)

    def for_service(self, service_name: str, since_days: int = 7) -> CatalogChangelog:
        """Aggregate all changes across every entity in a database service.

        Uses the search API to discover entities, then diffs each one's
        version history within the time window.

        Args:
            service_name: OM service name, e.g. 'my_service'.
            since_days: How many days back to scan.

        Returns:
            CatalogChangelog with scope 'service:{service_name}'.
        """
        now = datetime.now(tz=timezone.utc)
        from_date = now - timedelta(days=since_days)

        entities = self._client.search_entities(
            query=f"service.name:{service_name}",
            limit=200,
        )
        all_diffs = _diffs_for_entities(entities, self._differ, since_days)
        return _aggregate(f"service:{service_name}", from_date, now, all_diffs)

    def for_entity_type(self, entity_type: str, since_days: int = 7) -> CatalogChangelog:
        """Aggregate all changes across every entity of a given type.

        Args:
            entity_type: OM entity type, e.g. 'table'.
            since_days: How many days back to scan.

        Returns:
            CatalogChangelog with scope 'type:{entity_type}'.
        """
        now = datetime.now(tz=timezone.utc)
        from_date = now - timedelta(days=since_days)

        entities = self._client.search_entities(
            query="*",
            entity_type=entity_type,
            limit=200,
        )
        all_diffs = _diffs_for_entities(entities, self._differ, since_days)
        return _aggregate(f"type:{entity_type}", from_date, now, all_diffs)

    def for_user(self, username: str, since_days: int = 7) -> CatalogChangelog:
        """Aggregate all changes made by a specific user.

        Scans all entity types for version transitions where updatedBy
        matches the given username within the time window.

        Args:
            username: OM username, e.g. 'admin'.
            since_days: How many days back to scan.

        Returns:
            CatalogChangelog with scope 'user:{username}'.
        """
        now = datetime.now(tz=timezone.utc)
        from_date = now - timedelta(days=since_days)

        entities = self._client.search_entities(query="*", limit=200)
        all_diffs = _diffs_for_entities(entities, self._differ, since_days, user_filter=username)
        return _aggregate(f"user:{username}", from_date, now, all_diffs)

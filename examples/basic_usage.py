"""Quick-start: diff two versions of a table programmatically."""

from __future__ import annotations

import os

from ometa_diff.client import OMVersionClient
from ometa_diff.differ import MetadataDiffer

host = os.environ["OPENMETADATA_HOST"]
token = os.environ["OPENMETADATA_JWT_TOKEN"]

with OMVersionClient(host=host, token=token) as client:
    differ = MetadataDiffer(client)
    diff = differ.diff_entity(
        entity_type="table",
        fqn="my_service.prod_db.public.payments",
    )
    print(diff.summary)
    for change in diff.changes:
        print(f"  [{change.severity.upper()}] {change.field_path}: {change.change_type}")

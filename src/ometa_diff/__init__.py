"""ometa-diff — metadata version-diff intelligence for OpenMetadata."""

__version__ = "0.1.0b1"

from ometa_diff.client import OMVersionClient
from ometa_diff.exceptions import (
    NoDiffAvailable,
    OMAPIError,
    OMAuthError,
    OMConnectionError,
    OmetaDiffError,
    OMNotFoundError,
)
from ometa_diff.models import (
    CatalogChangelog,
    ChangeSeverity,
    ChangeType,
    EntityDiff,
    FieldChange,
    TopChanger,
)

__all__ = [
    "__version__",
    "OMVersionClient",
    "OmetaDiffError",
    "OMConnectionError",
    "OMAuthError",
    "OMNotFoundError",
    "OMAPIError",
    "NoDiffAvailable",
    "ChangeType",
    "ChangeSeverity",
    "FieldChange",
    "TopChanger",
    "EntityDiff",
    "CatalogChangelog",
]

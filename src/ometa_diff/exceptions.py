"""Custom exception hierarchy for ometa-diff."""


class OmetaDiffError(Exception):
    """Base exception for ometa-diff."""


class OMConnectionError(OmetaDiffError):
    """Cannot reach the OpenMetadata server."""


class OMAuthError(OmetaDiffError):
    """JWT token is invalid or missing."""


class OMNotFoundError(OmetaDiffError):
    """Entity not found (404 from OM API)."""


class OMAPIError(OmetaDiffError):
    """Unexpected error from OM API."""


class NoDiffAvailable(OmetaDiffError):
    """Entity has only one version — nothing to diff."""

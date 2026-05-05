"""Compliance exceptions (no FastAPI imports)."""


class ComplianceViolation(Exception):
    """Raised when an operation violates product / legal constraints."""

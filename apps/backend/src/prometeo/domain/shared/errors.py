"""Domain errors. Adapters translate these into transport-specific responses."""


class DomainError(Exception):
    """Base class for every rule violation detected by the domain."""


class UnitError(DomainError):
    """A unit is unknown or a conversion between incompatible dimensions was attempted."""


class InvalidMeasurementError(DomainError):
    """Inputs to a scientific calculation violate its assumptions."""


class NotFoundError(DomainError):
    """A requested entity does not exist."""

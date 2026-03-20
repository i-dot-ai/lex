"""Shared Qdrant filter building utilities."""

from enum import Enum

from qdrant_client.models import FieldCondition, Range


def build_year_range_conditions(
    year_from: int | None = None,
    year_to: int | None = None,
    year_field: str = "year",
) -> list[FieldCondition]:
    """Build Qdrant year-range filter conditions."""
    conditions = []
    if year_from is not None:
        conditions.append(FieldCondition(key=year_field, range=Range(gte=year_from)))
    if year_to is not None:
        conditions.append(FieldCondition(key=year_field, range=Range(lte=year_to)))
    return conditions


def extract_enum_values(items: list) -> list[str]:
    """Extract string values from a list that may contain enums or raw strings."""
    return [item.value if isinstance(item, Enum) else item for item in items]

import logging

from bs4 import BeautifulSoup

from .models import Amendment

logger = logging.getLogger(__name__)


class AmendmentParser:
    """
    Parser for amendments to legislation. Takes a BeautifulSoup object and returns a list of Amendment objects.
    """

    def __init__(
        self,
        base_url: str = "https://www.legislation.gov.uk",
    ):
        self.base_url = base_url

    def parse_content(self, soup: BeautifulSoup) -> list[Amendment]:
        table = soup.find("table")
        if not table:
            return []

        rows = table.find("tbody").find_all("tr")

        rows = [self._row_to_amendment(row) for row in rows]

        amendments = [row for row in rows if row is not None]

        if amendments:
            # Log successful parsing with structured data
            logger.info(
                f"Parsed {len(amendments)} amendments",
                extra={
                    "doc_type": "amendment",
                    "processing_status": "success",
                    "amendment_count": len(amendments),
                    # Sample first amendment for context
                    "sample_changed": amendments[0].changed_legislation if amendments else None,
                    "sample_affecting": amendments[0].affecting_legislation if amendments else None,
                },
            )

        return amendments

    def _row_to_amendment(self, row: BeautifulSoup) -> Amendment | None:
        """Convert a table row to an Amendment object.

        Returns:
            Amendment object, or None if the row references invalid/placeholder legislation
        """
        cols = row.find_all("td")

        changed_year, changed_number = self._get_year_number(cols[1].text)
        affecting_year, affecting_number = self._get_year_number(cols[5].text)
        changed_url = self._get_href_if_exists(cols[1])
        affecting_url = self._get_href_if_exists(cols[5])

        # Extract legislation identifier from URL (e.g., "ukpga/2002/1" from "/id/ukpga/2002/1")
        changed_leg_id = self._extract_leg_id_from_url(changed_url) if changed_url else None
        affecting_leg_id = self._extract_leg_id_from_url(affecting_url) if affecting_url else None

        # Skip amendments referencing placeholder/missing legislation
        if changed_leg_id and "/0000" in changed_leg_id:
            logger.debug(f"Skipping amendment - references missing legislation: {changed_leg_id}")
            return None

        if affecting_leg_id and "/0000" in affecting_leg_id:
            logger.debug(f"Skipping amendment - affecting legislation missing: {affecting_leg_id}")
            return None

        # Extract provision and type for unique ID
        changed_provision = cols[2].text.strip() if cols[2].text else None
        affecting_provision = cols[6].text.strip() if cols[6].text else None
        type_of_effect = cols[3].text.strip() if cols[3].text else None

        # Build unique ID including all distinguishing features
        id_parts = [
            f"changed-{changed_url}",
            f"prov-{changed_provision}" if changed_provision else "prov-none",
            f"affecting-{affecting_url}",
            f"prov-{affecting_provision}" if affecting_provision else "prov-none",
            f"type-{type_of_effect}" if type_of_effect else "type-none"
        ]
        unique_id = "-".join(id_parts)

        return Amendment(
            changed_legislation=changed_leg_id,
            changed_year=changed_year,
            changed_number=changed_number,
            changed_url=changed_url,
            changed_provision=changed_provision,
            changed_provision_url=self._get_href_if_exists(cols[2]),
            affecting_legislation=affecting_leg_id,
            affecting_year=affecting_year,
            affecting_number=affecting_number,
            affecting_url=affecting_url,
            affecting_provision=affecting_provision,
            affecting_provision_url=self._get_href_if_exists(cols[6]),
            type_of_effect=type_of_effect,
            id=unique_id,
        )

    def _get_href_if_exists(self, soup: BeautifulSoup) -> str | None:
        """Get href from soup if it exists."""
        x = soup.find("a")
        if x:
            try:
                return self.base_url + x["href"]
            except KeyError:
                return None
        return None

    def _extract_leg_id_from_url(self, url: str) -> str | None:
        """Extract legislation identifier from URL.

        Args:
            url: Full URL like "https://www.legislation.gov.uk/id/ukpga/2002/1"

        Returns:
            Legislation identifier like "ukpga/2002/1", or None if extraction fails
        """
        try:
            # Remove base URL and /id/ prefix
            # URL format: https://www.legislation.gov.uk/id/ukpga/2002/1
            if "/id/" in url:
                return url.split("/id/")[1]
            return None
        except (IndexError, AttributeError):
            return None

    def _get_year_number(self, text: str) -> tuple[int | None, str | None]:
        """Extract year and number from formatted text.

        Args:
            text: Formatted text like "2002 c. 1", "2017 No. 1283", or "2024 asc 1"

        Returns:
            Tuple of (year, number) where year is int and number is string
        """
        try:
            parts = text.split("\xa0")
            year = int(parts[0])

            # Extract number, handling various formats
            number_text = parts[1]

            # Format: "c. 1" (UKPGA)
            if number_text.startswith("c. "):
                number = number_text[3:]
            # Format: "No. 1283" (UKSI, WSI, SSI, etc.)
            elif number_text.startswith("No. "):
                number = number_text[4:]
            # Format: "asc 1", "asp 1", etc. (type code followed by number)
            elif " " in number_text:
                # Split and take the last part (the actual number)
                number = number_text.split()[-1]
            else:
                number = number_text

            return year, number
        except (IndexError, ValueError):
            return None, None

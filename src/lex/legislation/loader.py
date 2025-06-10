from pathlib import Path
from typing import Iterable

from bs4 import BeautifulSoup

from lex.core.loader import LexLoader
from lex.legislation.models import LegislationType


class LegislationLoader(LexLoader):
    """Loader for legislation content."""

    def __init__(self, input_path: str = "data/raw/legislation"):
        self.input_path = Path(input_path)

    def load_content(
        self,
        years: list[int],
        limit: int | None = None,
        types: list[LegislationType] = list(LegislationType),
    ) -> Iterable[str, BeautifulSoup]:
        """Load the content of the legislation files."""

        filenames = self._get_filenames(years, types, limit)
        sorted_filenames = self._sort_filenames(filenames)

        for filename in sorted_filenames:
            yield filename,self._load_xml_file(filename)

    def _get_filenames(
        self, years: list[int], types: list[LegislationType], limit: int | None = None
    ) -> list[Path]:
        """Get a list of filenames in the input path."""

        # We rely on the folder structure being {year}/{id}.xml within the input path
        folder_paths = [
            Path(self.input_path) / str(year)
            for year in years
            if (Path(self.input_path) / str(year)).exists()
        ]

        filenames = []

        for folder_path in folder_paths:
            # Add the files in the folder to the list if they end in .xml and start with any of the enum values
            for file in folder_path.glob("*.xml"):
                if any(file.name.startswith(type.value) for type in types):
                    filenames.append(file)

                if limit and len(filenames) >= limit:
                    return filenames

        return filenames

    def _sort_filenames(self, filenames: list[Path]) -> list[Path]:
        """Sort filenames by year (descending) then by legislation number (descending).

        Files that match the format {legislation_type}-{legislation_year}-{legislation_number}
        are sorted by their year first (newest to oldest), then by their number (largest to smallest).
        Files that don't match this format are placed at the beginning of the list.
        """

        # Helper function to extract legislation year and number
        def get_legislation_info(filename: Path) -> tuple[int, int] | None:
            # Expected format: {legislation_type}-{legislation_year}-{legislation_number}.xml
            parts = filename.stem.split("-")
            if len(parts) >= 3:
                try:
                    year = int(parts[1])
                    number = int(parts[2])
                    return (year, number)
                except ValueError:
                    return None
            return None

        # Group files by whether they match the expected format
        matching_files = []
        non_matching_files = []

        for file in filenames:
            info = get_legislation_info(file)
            if info is not None:
                year, number = info
                matching_files.append((file, year, number))
            else:
                non_matching_files.append(file)

        # Sort matching files by year (descending) then by legislation number (descending)
        sorted_matching_files = [
            file for file, _, _ in sorted(matching_files, key=lambda x: (x[1], x[2]), reverse=True)
        ]

        # Combine with non-matching files at the beginning
        return non_matching_files + sorted_matching_files

    def _load_xml_file(self, filename: Path) -> BeautifulSoup:
        with open(filename, "r", encoding="utf-8") as file:
            return BeautifulSoup(file.read(), "xml")

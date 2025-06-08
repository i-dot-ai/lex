import logging
from typing import Iterator

import requests
from bs4 import BeautifulSoup

from lex.core.checkpoint import PipelineCheckpoint
from lex.core.exceptions import RateLimitException
from lex.core.http import HttpClient
from lex.core.scraper import LexScraper
from lex.legislation.models import LegislationType

http_client = HttpClient()

logger = logging.getLogger(__name__)


class LegislationScraper(LexScraper):
    def __init__(self):
        self.base_url = "https://www.legislation.gov.uk"

    def load_content(
        self,
        years: list[int],
        limit: int | None = None,
        types: list[LegislationType] = list(LegislationType),
        use_checkpoint: bool = True,
        clear_checkpoint: bool = False,
    ) -> Iterator[BeautifulSoup]:
        """Scrapes legislation content from the internet with checkpoint support.
        
        Args:
            years: List of years to scrape
            limit: Maximum number of documents to process
            types: List of legislation types to process
            use_checkpoint: Whether to use checkpoint for resuming
            clear_checkpoint: Whether to clear existing checkpoint
        """
        # Create checkpoint ID based on parameters
        type_str = '_'.join(sorted(t.value for t in types))
        checkpoint_id = f"legislation_{min(years)}_{max(years)}_{type_str}"
        
        checkpoint = None
        processed_urls = set()
        completed_combinations = set()
        url_count = 0
        skipped_count = 0
        
        if use_checkpoint:
            checkpoint = PipelineCheckpoint(checkpoint_id)
            
            if clear_checkpoint:
                checkpoint.clear()
                logger.info(f"Cleared checkpoint: {checkpoint_id}")
            else:
                state = checkpoint.get_state()
                processed_urls = state['processed_urls']
                completed_combinations = checkpoint.get_completed_combinations()
                if processed_urls:
                    logger.info(
                        f"Resuming from checkpoint. Already processed: {len(processed_urls)} URLs, {len(completed_combinations)} completed combinations",
                        extra={
                            "checkpoint_id": checkpoint_id,
                            "processed_count": len(processed_urls),
                            "completed_combinations_count": len(completed_combinations),
                            "checkpoint_path": str(checkpoint.cache_dir)
                        }
                    )
                    
        logger.info(
            f"Starting to iterate through URLs (this may take time with large checkpoints)",
            extra={
                "checkpoint_id": checkpoint_id if checkpoint else None,
                "processed_count": len(processed_urls),
                "url_count_start": url_count
            }
        )

        # Track URLs per combination to know when complete
        combination_urls = {}
        current_combination = None
        combination_processed_count = 0
        
        try:
            for url in self.load_urls(years, types, limit, include_xml=True, completed_combinations=completed_combinations):
                url_count += 1
                
                # Extract combination from URL
                # URL format: https://www.legislation.gov.uk/{type}/{year}/{number}/data.xml
                parts = url.split('/')
                if len(parts) >= 6:
                    url_type = parts[3]
                    url_year = parts[4]
                    new_combination = f"{url_type}_{url_year}"
                    
                    # Check if we've moved to a new combination
                    if new_combination != current_combination:
                        # Mark previous combination as complete if all URLs were processed
                        if current_combination and checkpoint:
                            if current_combination not in combination_urls:
                                combination_urls[current_combination] = 0
                            if combination_processed_count == combination_urls[current_combination]:
                                checkpoint.mark_combination_complete(current_combination)
                                logger.info(f"Marked combination as complete: {current_combination}")
                        
                        current_combination = new_combination
                        combination_processed_count = 0
                        if current_combination not in combination_urls:
                            combination_urls[current_combination] = 0
                        combination_urls[current_combination] += 1
                
                # Skip if already processed
                if url in processed_urls:
                    skipped_count += 1
                    combination_processed_count += 1  # Still counts towards combination completion
                    # Log progress periodically while skipping
                    if url_count % 1000 == 0:
                        logger.info(
                            f"Checkpoint progress: Checked {url_count} URLs, skipped {skipped_count} already processed",
                            extra={
                                "checkpoint_id": checkpoint_id,
                                "urls_checked": url_count,
                                "urls_skipped": skipped_count,
                                "total_processed": len(processed_urls),
                                "completed_combinations": len(completed_combinations)
                            }
                        )
                    logger.debug(f"Skipping already processed: {url}")
                    continue
                
                try:
                    soup = self._load_legislation_from_url(url)
                    
                    # Mark as processed if using checkpoint
                    if checkpoint:
                        checkpoint.mark_processed(url)
                        combination_processed_count += 1
                        
                        # Save position periodically
                        if url_count % 100 == 0:
                            checkpoint.save_position(url_count)
                            checkpoint.update_metadata({
                                'years': f"{min(years)}-{max(years)}",
                                'types': type_str,
                                'total_urls': url_count
                            })
                    
                    yield soup
                    
                except RateLimitException as e:
                    # Save checkpoint before potential exit
                    if checkpoint:
                        checkpoint.save_position(url_count)
                        checkpoint.update_metadata({
                            'last_rate_limit': url,
                            'rate_limit_error': str(e)
                        })
                    
                    logger.warning(
                        f"Rate limit hit at position {url_count}",
                        extra={
                            "checkpoint_id": checkpoint_id if checkpoint else None,
                            "position": url_count,
                            "url": url,
                            "processed_count": len(processed_urls) + url_count
                        }
                    )
                    raise  # Re-raise to let pipeline handle
                    
                except Exception as e:
                    # Other errors - mark as failed but continue
                    error_msg = f"Failed to process {url}: {e}"
                    logger.error(error_msg, exc_info=True)
                    
                    if checkpoint:
                        checkpoint.mark_failed(url, str(e))
                    continue
                    
        finally:
            # Mark final combination as complete if all URLs were processed
            if current_combination and checkpoint:
                if combination_processed_count == combination_urls.get(current_combination, 0):
                    checkpoint.mark_combination_complete(current_combination)
                    logger.info(f"Marked final combination as complete: {current_combination}")
            
            # Log final summary if using checkpoint
            if checkpoint and checkpoint.exists():
                summary = checkpoint.get_summary()
                completed_count = len(checkpoint.get_completed_combinations())
                summary['completed_combinations'] = completed_count
                logger.info(
                    f"Checkpoint summary for {checkpoint_id}",
                    extra=summary
                )

    def load_urls(
        self,
        years: list[int],
        types: list[LegislationType],
        limit: int | None = None,
        include_xml=True,
        completed_combinations: set = None,
    ) -> Iterator[str]:
        count = 0
        if completed_combinations is None:
            completed_combinations = set()
            
        for year in years:
            for type in types:
                combination_key = f"{type.value}_{year}"
                
                # Skip if this combination is already complete
                if combination_key in completed_combinations:
                    logger.debug(f"Skipping completed combination: {combination_key}")
                    continue
                    
                urls = self._get_legislation_urls_from_type_year(type.value, year, include_xml)
                for url in urls:
                    yield url
                    count += 1
                    if limit and count >= limit:
                        return

    def _get_legislation_urls_from_type_year(
        self, legislation_type, year, include_xml=True
    ) -> Iterator[str]:
        url = f"{self.base_url}/{legislation_type}/{year}"
        logger.debug(f"Checking URL: {url}")
        
        try:
            res = http_client.get(url)
        except requests.exceptions.HTTPError as e:
            # Handle server errors gracefully
            if e.response is not None and e.response.status_code >= 500:
                logger.warning(
                    f"Server error accessing {legislation_type} for year {year}: {e.response.status_code}",
                    extra={
                        "url": url,
                        "status_code": e.response.status_code,
                        "legislation_type": legislation_type,
                        "year": year,
                        "error_type": "server_error"
                    }
                )
                return []
            else:
                # Re-raise other HTTP errors
                raise

        # Check if page exists with a reasonable status code
        if res.status_code != 200:
            logger.info(
                f"No {legislation_type} legislation found for year {year} (status: {res.status_code})"
            )
            return []

        soup = BeautifulSoup(res.text, "html.parser")

        # Check for "no results" message or missing content
        no_results_div = soup.find("div", class_="warning")
        if no_results_div and (
            "No items found for" in no_results_div.text
            or "Sorry, but we cannot satisfy your request" in no_results_div.text
        ):
            logger.info(f"No {legislation_type} legislation found for year {year}")
            return []

        next_page = url
        while next_page:
            logger.debug(f"Scraping {next_page}")
            try:
                res = http_client.get(next_page)
            except requests.exceptions.HTTPError as e:
                # Handle server errors gracefully
                if e.response is not None and e.response.status_code >= 500:
                    logger.warning(
                        f"Server error accessing page {next_page}: {e.response.status_code}",
                        extra={
                            "url": next_page,
                            "status_code": e.response.status_code,
                            "error_type": "server_error"
                        }
                    )
                    break  # Stop pagination on server error
                else:
                    # Re-raise other HTTP errors
                    raise
                    
            soup = BeautifulSoup(res.text, "html.parser")

            hrefs = self._extract_legislation_urls_from_searchpage(soup, legislation_type)

            if hrefs:
                # Filter out URLs that don't return valid XML
                for href in hrefs:
                    xml_url = self._get_data_xml_url_from_content_url(href)
                    if include_xml:
                        yield xml_url
                    else:
                        yield xml_url.replace("/data.xml", "")

            next_page = self._get_next_page_token(soup)

    def _get_next_page_token(self, soup):
        next_page = soup.find("a", title="next page")

        if next_page:
            return self.base_url + next_page["href"]
        else:
            return None

    def _extract_legislation_urls_from_searchpage(self, soup, legislation_type):
        hrefs = []
        valid_endswith = ["/contents/made", "/contents"]

        # Check if content div exists
        content_div = soup.find("div", id="content")
        if not content_div:
            logger.debug(f"No content div found for {legislation_type}")
            return hrefs

        # Check if table exists
        table = content_div.find("table")
        if not table:
            logger.debug(f"No table found for {legislation_type}")
            return hrefs

        # Check if tbody exists
        tbody = table.find("tbody")
        if not tbody:
            logger.debug(f"No tbody found for {legislation_type}")
            return hrefs

        for row in tbody.find_all("tr"):
            cells = row.find_all("td")
            if not cells:
                continue

            cell = cells[0]
            a_tag = cell.find("a")
            if not a_tag or "href" not in a_tag.attrs:
                continue

            href = a_tag["href"]
            if href.startswith(f"/{legislation_type}") and href.endswith(tuple(valid_endswith)):
                # Just store the base URL (without /data.xml) for now
                # We'll validate and process later
                base_url = self.base_url + "/".join(href.split("/")[:4])
                hrefs.append(base_url)

        return hrefs

    def _get_data_xml_url_from_content_url(self, url):
        """
        Convert a URL like https://www.legislation.gov.uk/ukpga/2022/1
        to a data.xml URL like https://www.legislation.gov.uk/ukpga/2022/1/data.xml

        Args:
            url: Content URL

        Returns:
            Data XML URL
        """
        # Remove any trailing slash
        url = url.rstrip("/")

        # Check if URL already ends with /data.xml
        if url.endswith("/data.xml"):
            return url

        # Check if URL contains /contents - we need to remove this
        if "/contents" in url:
            url = url.split("/contents")[0]

        # Return with /data.xml appended
        return f"{url}/data.xml"

    def _load_legislation_from_url(self, url: str) -> BeautifulSoup:
        res = http_client.get(url)
        soup = BeautifulSoup(res.text, "xml")
        return soup

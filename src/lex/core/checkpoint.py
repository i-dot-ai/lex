"""Pipeline checkpoint system for resilient processing."""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, Optional, Set

from diskcache import Cache

from lex.core.error_utils import ErrorCategorizer
from lex.core.exceptions import ProcessedException

logger = logging.getLogger(__name__)


class CheckpointCombination:
    """Represents a single checkpoint combination with its own checkpoint file."""

    def __init__(self, year: int, doc_type: Any, doc_type_name: str, **kwargs):
        self.year = year
        self.doc_type = doc_type  # LegislationType.UKPGA, Court.UKSC, or None

        # Each combination gets its own checkpoint file
        if doc_type is None:
            # Amendments case
            checkpoint_id = f"{doc_type_name}_{year}"
        else:
            # All other cases: legislation_ukpga_2023, caselaw_uksc_2022
            checkpoint_id = f"{doc_type_name}_{doc_type.value}_{year}"

        self.checkpoint_manager = PipelineCheckpoint(checkpoint_id)

        # Handle clear_checkpoint if requested
        if kwargs.get('clear_checkpoint', False):
            self.checkpoint_manager.clear()

    def is_complete(self) -> bool:
        """Check if this combination has been marked as complete."""
        return self.checkpoint_manager.cache.get(self.checkpoint_manager._get_key("combination_complete"), False)

    def is_processed(self, url: str) -> bool:
        """Check if URL has already been successfully processed."""
        return url in self.checkpoint_manager.get_processed_urls()

    def mark_limit_hit(self):
        """Mark that this combination has hit its processing limit."""
        self.checkpoint_manager.mark_limit_hit()

    def process_item(self, url: str, processor_func: Callable[[], Any]) -> Optional[Any]:
        """
        Process an item with automatic checkpoint tracking.

        Args:
            url: Unique identifier for this item
            processor_func: Function that processes the item (e.g., parser.parse_content)

        Returns:
            Result of processor_func if successful, None if already processed

        Raises:
            Exception: Re-raises any exception from processor_func after marking as failed
        """
        if self.is_processed(url):
            logger.debug(f"Skipping already processed URL: {url}")
            return None

        try:
            result = processor_func()
            self.checkpoint_manager.mark_processed(url)
            logger.debug(f"Successfully processed URL: {url}")
            return result
        except ProcessedException as e:
            # Mark as processed even though parsing failed - we don't want to retry
            self.checkpoint_manager.mark_processed(url)
            logger.info(f"Marking URL as processed despite failure: {url} - {str(e)}")
            return None
        except Exception as e:
            self.checkpoint_manager.mark_failed(url, str(e))

            ErrorCategorizer.handle_error(logger, e, url)
            return None

    def __enter__(self):
        """Start processing this combination."""
        if self.is_complete():
            logger.info(f"Skipping completed combination: {self.checkpoint_manager.checkpoint_id}")
        else:
            logger.info(f"Starting combination: {self.checkpoint_manager.checkpoint_id}")
            # Clear hit_limit flag when starting fresh processing
            self.checkpoint_manager.clear_limit_hit()

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Mark combination complete based on processing state, not exceptions."""
        failed_urls = self.checkpoint_manager.cache.get(
            self.checkpoint_manager._get_key("failed_urls"), {}
        )

        has_failed_urls = len(failed_urls) > 0
        has_hit_limit = self.checkpoint_manager.has_hit_limit()

        # Only mark complete if:
        # - No failed URLs (nothing to retry)
        # - AND didn't hit limit (no more items to process)
        should_complete = not has_failed_urls and not has_hit_limit

        if should_complete:
            self.checkpoint_manager.cache.set(
                self.checkpoint_manager._get_key("combination_complete"), True
            )
            self.checkpoint_manager.cache.set(
                self.checkpoint_manager._get_key("updated_at"), datetime.now().isoformat()
            )
            logger.info(f"Marked {self.checkpoint_manager.checkpoint_id} as complete")
        else:
            # Log why it wasn't marked complete
            reasons = []
            if has_failed_urls:
                reasons.append(f"{len(failed_urls)} failed URLs")
            if has_hit_limit:
                reasons.append("hit processing limit")

            logger.info(
                f"Not marking {self.checkpoint_manager.checkpoint_id} as complete: {', '.join(reasons)}"
            )


def get_checkpoints(
    years: list[int],
    types: list[Any] = None,
    doc_type_name: str = None,
    **kwargs
) -> Iterator[CheckpointCombination]:
    """
    Generate checkpoint combinations, skipping completed ones.

    Args:
        years: List of years to process
        types: List of document types (LegislationType, Court, etc.) - None for amendments
        doc_type_name: Document type string for checkpoint naming
        **kwargs: Additional checkpoint options (clear_checkpoint, etc.)

    Returns:
        Iterator of CheckpointCombination objects
    """

    if types is None:
        # Amendments case - just years
        for year in years:
            combination = CheckpointCombination(year, None, doc_type_name, **kwargs)
            if not combination.is_complete():
                yield combination
    else:
        # All other cases - year × type combinations
        for year in years:
            for doc_type_val in types:
                combination = CheckpointCombination(year, doc_type_val, doc_type_name, **kwargs)
                if not combination.is_complete():
                    yield combination


class PipelineCheckpoint:
    """Manages checkpoint state for pipeline runs using mounted volume."""

    def __init__(self, checkpoint_id: str, base_dir: str = None):
        """
        Initialize checkpoint manager.

        Args:
            checkpoint_id: Unique identifier for this checkpoint. For example: "legislation_ukpga_2023"
            base_dir: Base directory for checkpoints (auto-detected if None)
        """
        self.checkpoint_id = checkpoint_id

        # Use mounted volume in container or local data dir
        if base_dir is None:
            if os.path.exists("/app/data"):
                base_dir = "/app/data/checkpoints"
            else:
                base_dir = os.path.join(os.getcwd(), "data", "checkpoints")

        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

        # Use shared cache with prefixed keys instead of separate directories
        self.cache = Cache(str(self.base_dir))
        self._key_prefix = f"{checkpoint_id}:"

        logger.debug(
            f"Checkpoint initialized: {checkpoint_id}",
            extra={"checkpoint_id": checkpoint_id, "checkpoint_path": str(self.base_dir)},
        )

    def _get_key(self, key: str) -> str:
        """Get prefixed key for cache operations."""
        return f"{self._key_prefix}{key}"

    def get_state(self) -> Dict[str, Any]:
        """Get current checkpoint state."""
        return {
            "processed_urls": set(self.cache.get(self._get_key("processed_urls"), [])),
            "failed_urls": dict(self.cache.get(self._get_key("failed_urls"), {})),
            "hit_limit": self.cache.get(self._get_key("hit_limit"), False),
            "last_position": self.cache.get(self._get_key("last_position"), 0),
            "metadata": self.cache.get(self._get_key("metadata"), {}),
            "created_at": self.cache.get(self._get_key("created_at"), datetime.now().isoformat()),
            "updated_at": self.cache.get(self._get_key("updated_at"), datetime.now().isoformat()),
        }

    def get_processed_urls(self) -> Set[str]:
        """Get set of processed URLs."""
        return set(self.cache.get(self._get_key("processed_urls"), []))

    def mark_processed(self, url: str):
        """Mark a URL as successfully processed."""
        processed = set(self.cache.get(self._get_key("processed_urls"), []))
        processed.add(url)
        self.cache.set(self._get_key("processed_urls"), list(processed))
        self.cache.set(self._get_key("updated_at"), datetime.now().isoformat())

    def mark_failed(self, url: str, error: str):
        """Mark a URL as failed with error details."""
        failed = dict(self.cache.get(self._get_key("failed_urls"), {}))
        failed[url] = {"error": error, "timestamp": datetime.now().isoformat()}
        self.cache.set(self._get_key("failed_urls"), failed)
        self.cache.set(self._get_key("updated_at"), datetime.now().isoformat())


    def mark_limit_hit(self):
        """Mark that this combination has hit its processing limit."""
        self.cache.set(self._get_key("hit_limit"), True)
        self.cache.set(self._get_key("updated_at"), datetime.now().isoformat())
        logger.debug(f"Marked {self.checkpoint_id} as having hit limit")

    def clear_limit_hit(self):
        """Clear the hit_limit flag - indicates we can process more if needed."""
        self.cache.set(self._get_key("hit_limit"), False)
        self.cache.set(self._get_key("updated_at"), datetime.now().isoformat())
        logger.debug(f"Cleared hit limit flag for {self.checkpoint_id}")

    def has_hit_limit(self) -> bool:
        """Check if this combination has hit its processing limit."""
        return self.cache.get(self._get_key("hit_limit"), False)

    def save_position(self, position: int):
        """Save current position in iteration."""
        self.cache.set(self._get_key("last_position"), position)
        self.cache.set(self._get_key("updated_at"), datetime.now().isoformat())

    def update_metadata(self, metadata: Dict[str, Any]):
        """Update checkpoint metadata."""
        current_metadata = self.cache.get(self._get_key("metadata"), {})
        current_metadata.update(metadata)
        self.cache.set(self._get_key("metadata"), current_metadata)
        self.cache.set(self._get_key("updated_at"), datetime.now().isoformat())



    def clear(self):
        """Clear checkpoint data for this specific checkpoint."""
        deleted_count = 0

        # Much more efficient: use SQL pattern matching instead of iterating all keys
        try:
            # Use SQL LIKE for pattern-based deletion (avoids scanning all keys)
            with self.cache.transact():
                cursor = self.cache._sql(
                    'DELETE FROM Cache WHERE key LIKE ?',
                    (f'{self._key_prefix}%',)
                )
                deleted_count = cursor.rowcount

        except (AttributeError, Exception) as e:
            # Fallback to iteration if SQL access fails
            logger.warning(f"SQL deletion failed, falling back to iteration: {e}")
            with self.cache.transact():
                # Track our own keys to avoid full scan
                known_keys = [
                    "processed_urls", "failed_urls", "metadata",
                    "created_at", "updated_at", "combination_complete", "last_position"
                ]
                for key_suffix in known_keys:
                    full_key = self._get_key(key_suffix)
                    if full_key in self.cache:
                        del self.cache[full_key]
                        deleted_count += 1

        logger.info(f"Checkpoint cleared: {self.checkpoint_id} ({deleted_count} keys removed)")
        return None  # Explicitly return None to avoid printing numbers in notebooks

    def exists(self) -> bool:
        """Check if checkpoint has data."""
        return len(self.cache) > 0

    def get_summary(self) -> Dict[str, Any]:
        """Get checkpoint summary for logging."""
        state = self.get_state()
        failed_count = len(state["failed_urls"])
        processed_count = len(state["processed_urls"])

        return {
            "checkpoint_id": self.checkpoint_id,
            "processed_count": processed_count,
            "failed_count": failed_count,
            "last_position": state["last_position"],
            "created_at": state["created_at"],
            "updated_at": state["updated_at"],
            "has_failures": failed_count > 0,
        }

    @classmethod
    def list_checkpoints(cls, base_dir: str = None) -> list[str]:
        """List all available checkpoints."""
        if base_dir is None:
            if os.path.exists("/app/data"):
                base_dir = "/app/data/checkpoints"
            else:
                base_dir = os.path.join(os.getcwd(), "data", "checkpoints")

        base_path = Path(base_dir)
        if not base_path.exists():
            return []

        return [d.name for d in base_path.iterdir() if d.is_dir()]

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensure cache is closed."""
        # Diskcache handles cleanup automatically
        pass

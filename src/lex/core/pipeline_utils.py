"""Pipeline utilities for cross-cutting concerns like monitoring, logging, and checkpointing."""

import logging
import time
from functools import wraps
from typing import Any, Callable, Dict, Iterator, Optional, TypeVar, List, Set, Tuple
from datetime import datetime
from contextlib import contextmanager
import re

from lex.core.models import LexModel
from lex.core.checkpoint import PipelineCheckpoint

T = TypeVar('T', bound=LexModel)


class PipelineMonitor:
    """Decorator for pipeline monitoring and structured logging.
    
    This decorator adds consistent logging, error handling, and performance
    monitoring to pipeline functions without cluttering the business logic.
    """
    
    def __init__(self, doc_type: str, track_progress: bool = True, 
                 progress_interval: int = 10):
        """Initialize the pipeline monitor.
        
        Args:
            doc_type: The type of document being processed (e.g., 'legislation', 'caselaw')
            track_progress: Whether to log progress updates
            progress_interval: Seconds between progress updates
        """
        self.doc_type = doc_type
        self.track_progress = track_progress
        self.progress_interval = progress_interval
        
    def __call__(self, func: Callable[..., Iterator[T]]) -> Callable[..., Iterator[T]]:
        """Wrap the pipeline function with monitoring capabilities."""
        
        @wraps(func)
        def wrapper(*args, **kwargs) -> Iterator[T]:
            logger = logging.getLogger(func.__module__)
            start_time = time.time()
            doc_count = 0
            error_count = 0
            pdf_fallback_count = 0
            last_progress_time = start_time
            
            # Extract meaningful parameters for logging
            params_info = self._extract_params_info(args, kwargs)
            
            logger.info(
                f"Starting {self.doc_type} pipeline",
                extra={
                    "doc_type": self.doc_type,
                    "pipeline_status": "started",
                    **params_info
                }
            )
            
            try:
                for doc in func(*args, **kwargs):
                    doc_count += 1
                    
                    # Log successful processing with document metadata
                    doc_metadata = self._extract_doc_metadata(doc)
                    logger.info(
                        f"Processed {self.doc_type} document",
                        extra={
                            "doc_type": self.doc_type,
                            "processing_status": "success",
                            "doc_count": doc_count,
                            **doc_metadata
                        }
                    )
                    
                    # Progress tracking
                    if self.track_progress:
                        current_time = time.time()
                        if current_time - last_progress_time >= self.progress_interval:
                            elapsed = current_time - start_time
                            rate = doc_count / elapsed if elapsed > 0 else 0
                            
                            logger.info(
                                f"Pipeline progress: {doc_count} documents processed",
                                extra={
                                    "doc_type": self.doc_type,
                                    "pipeline_status": "in_progress",
                                    "doc_count": doc_count,
                                    "elapsed_seconds": elapsed,
                                    "docs_per_second": rate,
                                    "error_count": error_count,
                                    "pdf_fallback_count": pdf_fallback_count
                                }
                            )
                            last_progress_time = current_time
                    
                    yield doc
                    
            except Exception as e:
                error_count += 1
                error_metadata = self._extract_error_metadata(e, args, kwargs)
                
                # Check if it's a PDF fallback
                if self._is_pdf_fallback(e):
                    pdf_fallback_count += 1
                    error_metadata["processing_status"] = "pdf_fallback"
                else:
                    error_metadata["processing_status"] = "error"
                
                logger.error(
                    f"Error in {self.doc_type} pipeline: {str(e)}",
                    exc_info=True,
                    extra={
                        "doc_type": self.doc_type,
                        "error_type": type(e).__name__,
                        "error_count": error_count,
                        **error_metadata
                    }
                )
                raise
                
            finally:
                # Final summary
                elapsed = time.time() - start_time
                rate = doc_count / elapsed if elapsed > 0 else 0
                
                logger.info(
                    f"Completed {self.doc_type} pipeline: {doc_count} documents in {elapsed:.2f}s",
                    extra={
                        "doc_type": self.doc_type,
                        "pipeline_status": "completed",
                        "total_docs": doc_count,
                        "total_errors": error_count,
                        "pdf_fallbacks": pdf_fallback_count,
                        "elapsed_seconds": elapsed,
                        "docs_per_second": rate,
                        **params_info
                    }
                )
        
        return wrapper
    
    def _extract_params_info(self, args: tuple, kwargs: dict) -> Dict[str, Any]:
        """Extract relevant parameters for logging."""
        info = {}
        
        # Common parameters across pipelines
        if 'years' in kwargs:
            info['years'] = kwargs['years']
        elif len(args) > 1 and isinstance(args[1], list):
            info['years'] = args[1]
            
        if 'types' in kwargs:
            info['types'] = kwargs['types']
        elif len(args) > 0 and isinstance(args[0], list):
            info['types'] = args[0]
            
        if 'limit' in kwargs:
            info['limit'] = kwargs['limit']
            
        return info
    
    def _extract_doc_metadata(self, doc: T) -> Dict[str, Any]:
        """Extract metadata from a document for logging."""
        metadata = {}
        
        # Common fields across document types
        if hasattr(doc, 'id'):
            metadata['doc_id'] = doc.id
            
            # Try to extract year and type from ID
            year_match = re.search(r'/(\d{4})/', str(doc.id))
            if year_match:
                metadata['doc_year'] = int(year_match.group(1))
                
            type_match = re.search(r'/([a-z]+)/', str(doc.id))
            if type_match:
                metadata['doc_subtype'] = type_match.group(1)
                
        if hasattr(doc, 'title'):
            metadata['doc_title'] = doc.title[:100]  # Truncate long titles
            
        return metadata
    
    def _extract_error_metadata(self, error: Exception, args: tuple, kwargs: dict) -> Dict[str, Any]:
        """Extract metadata from an error for structured logging."""
        metadata = {}
        
        # Try to extract document information from error message
        error_msg = str(error)
        
        # Extract URL if present
        url_match = re.search(r'https?://[^\s]+', error_msg)
        if url_match:
            metadata['error_url'] = url_match.group(0)
            
        # Extract document ID if present
        id_match = re.search(r'/(ukpga|uksi|ukla|[a-z]+)/(\d{4})/(\d+)', error_msg)
        if id_match:
            metadata['doc_id'] = f"{id_match.group(1)}/{id_match.group(2)}/{id_match.group(3)}"
            metadata['doc_type_specific'] = id_match.group(1)
            metadata['doc_year'] = int(id_match.group(2))
            
        return metadata
    
    def _is_pdf_fallback(self, error: Exception) -> bool:
        """Check if the error indicates a PDF fallback."""
        error_msg = str(error).lower()
        return "no body found" in error_msg or "likely a pdf" in error_msg


class CheckpointManager:
    """Context manager for consistent checkpointing across pipelines.
    
    This manager handles checkpoint lifecycle, combination tracking, and
    failure recording in a consistent way across all document types.
    """
    
    def __init__(self, doc_type: str, use_checkpoint: bool = True, 
                 clear_checkpoint: bool = False, suffix: Optional[str] = None):
        """Initialize checkpoint manager.
        
        Args:
            doc_type: Type of documents being processed
            use_checkpoint: Whether to use checkpointing
            clear_checkpoint: Whether to clear existing checkpoint
            suffix: Optional suffix for checkpoint naming
        """
        self.doc_type = doc_type
        self.use_checkpoint = use_checkpoint
        self.clear_checkpoint = clear_checkpoint
        self.suffix = suffix
        self.checkpoint: Optional[PipelineCheckpoint] = None
        self.logger = logging.getLogger(__name__)
        
    def __enter__(self) -> 'CheckpointManager':
        """Enter the context and initialize checkpoint if needed."""
        if self.use_checkpoint:
            checkpoint_name = f"{self.doc_type}_pipeline"
            if self.suffix:
                checkpoint_name = f"{checkpoint_name}_{self.suffix}"
                
            self.checkpoint = PipelineCheckpoint(checkpoint_name)
            
            if self.clear_checkpoint:
                self.checkpoint.clear()
                self.logger.info(f"Cleared checkpoint for {checkpoint_name}")
            else:
                stats = self.get_stats()
                self.logger.info(
                    f"Resuming from checkpoint: {stats['processed']} processed, "
                    f"{stats['failed']} failed, {stats['completed']} combinations completed"
                )
                
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context and log final stats."""
        if self.checkpoint:
            stats = self.get_stats()
            self.logger.info(
                f"Checkpoint final stats: {stats['processed']} processed, "
                f"{stats['failed']} failed, {stats['completed']} combinations completed"
            )
            
    def is_processed(self, url: str) -> bool:
        """Check if a URL has been processed."""
        if not self.checkpoint:
            return False
        return self.checkpoint.is_processed(url)
    
    def mark_processed(self, url: str, metadata: Optional[Dict[str, Any]] = None):
        """Mark a URL as processed."""
        if self.checkpoint:
            self.checkpoint.add_processed(url, metadata)
            
    def mark_failed(self, url: str, error: Exception, metadata: Optional[Dict[str, Any]] = None):
        """Mark a URL as failed with error details."""
        if self.checkpoint:
            error_info = {
                "error_type": type(error).__name__,
                "error_message": str(error),
                "timestamp": datetime.now().isoformat()
            }
            if metadata:
                error_info.update(metadata)
            self.checkpoint.add_failed(url, error_info)
            
    def is_combination_completed(self, combination: str) -> bool:
        """Check if a combination (e.g., 'ukpga_2023') is completed."""
        if not self.checkpoint:
            return False
        return self.checkpoint.is_combination_completed(combination)
    
    def mark_combination_completed(self, combination: str):
        """Mark a combination as completed."""
        if self.checkpoint:
            self.checkpoint.mark_combination_completed(combination)
            
    def get_position(self, key: str) -> Optional[Any]:
        """Get saved position for resuming iteration."""
        if not self.checkpoint:
            return None
        return self.checkpoint.get_position(key)
    
    def save_position(self, key: str, position: Any):
        """Save position for resuming iteration."""
        if self.checkpoint:
            self.checkpoint.save_position(key, position)
            
    def get_stats(self) -> Dict[str, int]:
        """Get checkpoint statistics."""
        if not self.checkpoint:
            return {"processed": 0, "failed": 0, "completed": 0}
            
        return {
            "processed": len(self.checkpoint.get_processed_urls()),
            "failed": len(self.checkpoint.get_failed_urls()),
            "completed": len(self.checkpoint.get_completed_combinations())
        }
    
    def should_process_combination(self, types: List[str], years: List[int]) -> Iterator[Tuple[str, int]]:
        """Yield combinations that should be processed, skipping completed ones.
        
        Args:
            types: List of document types
            years: List of years
            
        Yields:
            Tuples of (type, year) that need processing
        """
        for doc_type in types:
            for year in years:
                combination = f"{doc_type}_{year}"
                
                if self.is_combination_completed(combination):
                    self.logger.info(f"Skipping completed combination: {combination}")
                    continue
                    
                yield doc_type, year
                
    def process_with_recovery(self, items: Iterator[Any], 
                            process_func: Callable[[Any], Optional[T]],
                            get_url_func: Callable[[Any], str]) -> Iterator[T]:
        """Process items with checkpoint-based recovery.
        
        Args:
            items: Iterator of items to process
            process_func: Function to process each item
            get_url_func: Function to extract URL from item for checkpointing
            
        Yields:
            Processed items (skipping failures)
        """
        for item in items:
            url = get_url_func(item)
            
            # Skip if already processed
            if self.is_processed(url):
                continue
                
            try:
                result = process_func(item)
                if result:
                    self.mark_processed(url)
                    yield result
            except Exception as e:
                self.logger.error(f"Error processing {url}: {e}")
                self.mark_failed(url, e)
                # Continue processing other items instead of failing


@contextmanager
def checkpoint_manager(doc_type: str, use_checkpoint: bool = True,
                      clear_checkpoint: bool = False, suffix: Optional[str] = None):
    """Convenience function to create a CheckpointManager context.
    
    Usage:
        with checkpoint_manager("legislation", use_checkpoint=True) as mgr:
            for type_name, year in mgr.should_process_combination(types, years):
                # Process combination
                mgr.mark_combination_completed(f"{type_name}_{year}")
    """
    manager = CheckpointManager(doc_type, use_checkpoint, clear_checkpoint, suffix)
    with manager as mgr:
        yield mgr
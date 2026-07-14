"""Base collector class for cloud resource inventory."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, List
import importlib
import json
import logging
import random
import sys
import time

logger = logging.getLogger(__name__)

TRANSIENT_KEYWORDS = frozenset([
    "throttl", "rate", "toomany", "429", "503", "retry",
    "timeout", "temporarily", "unavailable", "connection",
])


def _is_transient(exc: Exception) -> bool:
    """Heuristic check for transient/retriable errors based on common status codes and keywords."""
    exc_str = str(exc).lower()
    exc_type = type(exc).__name__.lower()
    combined = f"{exc_type} {exc_str}"
    return any(kw in combined for kw in TRANSIENT_KEYWORDS)


def retry_api_call(func, *args, max_retries: int = 3, base_delay: float = 1.0, **kwargs):
    """
    Call *func* with retry + exponential backoff for transient errors.

    Auth/permission errors are never retried.  The final attempt re-raises
    the original exception so the caller's error handling is unchanged.
    """
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if attempt == max_retries or not _is_transient(exc):
                raise
            delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
            logger.warning(
                "Transient error (attempt %d/%d), retrying in %.1fs: %s",
                attempt + 1, max_retries + 1, delay, exc
            )
            time.sleep(delay)
    raise last_exc  # unreachable, satisfies type checker


def require_import(module_path: str, package_name: str, provider: str):
    """Import a module or raise a helpful ImportError with install instructions."""
    try:
        return importlib.import_module(module_path)
    except ImportError as exc:
        raise ImportError(
            f"{package_name} is required. "
            f"Install with: \"{sys.executable}\" -m pip install "
            f"\"lm-cloud-inventory[{provider}]\"\n"
            f"  Underlying error: {exc}"
        ) from exc


class BaseCollector(ABC):
    """
    Abstract base class for cloud resource collectors.
    
    All provider-specific collectors must inherit from this class
    and implement the required abstract methods.
    """

    PROVIDER: str = ""

    def __init__(self):
        """Initialize the collector."""
        self._inventory: List[Dict] = []

    @abstractmethod
    def collect(self) -> List[Dict]:
        """
        Collect resources and return standardized inventory.
        
        Returns:
            List of resource records with schema:
            {
                "provider": str,
                "account_id": str,
                "region": str,
                "resource_type": str,
                "count": int,
                "timestamp": str  (ISO 8601)
            }
        """

    @abstractmethod
    def validate_permissions(self) -> bool:
        """
        Check if required permissions are available.
        
        Returns:
            True if all required permissions are available, False otherwise.
        """

    @abstractmethod
    def get_account_id(self) -> str:
        """
        Get the current account/subscription/project identifier.
        
        Returns:
            String identifier for the current account context.
        """

    def create_inventory_record(
        self,
        account_id: str,
        region: str,
        resource_type: str,
        count: int
    ) -> Dict:
        """
        Create a standardized inventory record.
        
        Args:
            account_id: Account/Subscription/Project ID
            region: Resource region/location
            resource_type: Provider-specific resource type
            count: Number of resources
            
        Returns:
            Standardized inventory record dictionary.
        """
        return {
            "provider": self.PROVIDER,
            "account_id": account_id,
            "region": region,
            "resource_type": resource_type,
            "count": count,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def save_inventory(self, output_path: str, inventory: List[Dict] = None) -> None:
        """
        Save inventory to a JSON file.
        
        Args:
            output_path: Path to output file.
            inventory: Optional inventory list. Uses self._inventory if not provided.
        """
        data = inventory if inventory is not None else self._inventory
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)
        logger.info("Saved inventory to %s", output_path)

    def print_summary(self, inventory: List[Dict] = None) -> None:
        """
        Print a summary of collected resources.
        
        Args:
            inventory: Optional inventory list. Uses self._inventory if not provided.
        """
        data = inventory if inventory is not None else self._inventory

        type_counts = {}
        total_resources = 0

        for record in data:
            resource_type = record["resource_type"]
            count = record["count"]
            type_counts[resource_type] = type_counts.get(resource_type, 0) + count
            total_resources += count

        print(f"\n{'='*60}")
        print(f"Inventory Summary - {self.PROVIDER.upper()}")
        print(f"{'='*60}")
        print(f"Total Resource Types: {len(type_counts)}")
        print(f"Total Resources: {total_resources}")
        print(f"{'='*60}")

        sorted_types = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)
        for resource_type, count in sorted_types[:20]:
            print(f"  {resource_type}: {count}")

        if len(sorted_types) > 20:
            print(f"  ... and {len(sorted_types) - 20} more resource types")

        print(f"{'='*60}\n")

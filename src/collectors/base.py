"""Base collector class for cloud resource inventory."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, List, Optional
import json
import logging

logger = logging.getLogger(__name__)


class BaseCollector(ABC):
    """
    Abstract base class for cloud resource collectors.
    
    All provider-specific collectors must inherit from this class
    and implement the required abstract methods.
    """

    # Provider identifier (aws, azure, gcp, oci)
    PROVIDER: str = ""

    def __init__(self, resource_mappings: Dict = None):
        """
        Initialize the collector.
        
        Args:
            resource_mappings: Optional dict mapping resource types to categories.
                             If not provided, loads from config/resource_mappings.json.
        """
        self.resource_mappings = resource_mappings or {}
        self._inventory: List[Dict] = []

    @abstractmethod
    def collect(self) -> List[Dict]:
        """
        Collect resources and return standardized inventory.
        
        Returns:
            List of resource records with schema:
            {
                "provider": str,          # aws, azure, gcp, oci
                "account_id": str,        # Account/Subscription/Project/Tenancy ID
                "region": str,            # Resource region/location
                "resource_type": str,     # Provider-specific resource type
                "count": int,             # Number of resources
                "timestamp": str          # ISO 8601 timestamp
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

    def get_category(self, resource_type: str) -> Optional[str]:
        """
        Get the license category for a resource type.
        
        Args:
            resource_type: Provider-specific resource type string.
            
        Returns:
            Category string (IaaS, PaaS, Non-Compute) or None if not mapped.
        """
        provider_mappings = self.resource_mappings.get(self.PROVIDER, {})
        resource_info = provider_mappings.get(resource_type, {})
        return resource_info.get("category")

    def save_inventory(self, output_path: str, inventory: List[Dict] = None) -> None:
        """
        Save inventory to a JSON file.
        
        Args:
            output_path: Path to output file.
            inventory: Optional inventory list. Uses self._inventory if not provided.
        """
        data = inventory or self._inventory
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)
        logger.info("Saved inventory to %s", output_path)

    def print_summary(self, inventory: List[Dict] = None) -> None:
        """
        Print a summary of collected resources.
        
        Args:
            inventory: Optional inventory list. Uses self._inventory if not provided.
        """
        data = inventory or self._inventory

        # Aggregate by resource type
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

        # Sort by count descending
        sorted_types = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)
        for resource_type, count in sorted_types[:20]:  # Top 20
            print(f"  {resource_type}: {count}")

        if len(sorted_types) > 20:
            print(f"  ... and {len(sorted_types) - 20} more resource types")

        print(f"{'='*60}\n")

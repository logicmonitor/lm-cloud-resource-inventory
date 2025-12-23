"""GCP Cloud Asset Inventory collector for resource inventory."""

import logging
from typing import Dict, List, Optional

from .base import BaseCollector

logger = logging.getLogger(__name__)


class GCPCollector(BaseCollector):
    """
    GCP resource collector using Cloud Asset Inventory API.
    
    Cloud Asset Inventory provides a unified view of all resources
    across projects, folders, and organizations.
    """

    PROVIDER = "gcp"

    def __init__(
        self,
        resource_mappings: Dict = None,
        project_id: str = None,
        organization_id: str = None,
        folder_id: str = None
    ):
        """
        Initialize the GCP collector.
        
        Args:
            resource_mappings: Optional dict mapping resource types to categories.
            project_id: GCP project ID to query (for project-scoped collection).
            organization_id: GCP organization ID (for org-wide collection).
            folder_id: GCP folder ID (for folder-scoped collection).
        """
        super().__init__(resource_mappings)
        self.project_id = project_id
        self.organization_id = organization_id
        self.folder_id = folder_id
        self._client = None

    def _get_client(self):
        """Get Cloud Asset Inventory client."""
        if self._client is None:
            try:
                from google.cloud import asset_v1
                self._client = asset_v1.AssetServiceClient()
            except ImportError as exc:
                raise ImportError(
                    "google-cloud-asset package is required. "
                    "Install with: pip install google-cloud-asset"
                ) from exc
        return self._client

    def _get_scope(self) -> str:
        """
        Get the scope for asset queries.
        
        Returns:
            Scope string (organizations/X, folders/X, or projects/X).
        """
        if self.organization_id:
            return f"organizations/{self.organization_id}"
        elif self.folder_id:
            return f"folders/{self.folder_id}"
        elif self.project_id:
            return f"projects/{self.project_id}"
        else:
            # Try to get default project from environment
            import os
            project = os.environ.get('GOOGLE_CLOUD_PROJECT') or os.environ.get('GCLOUD_PROJECT')
            if project:
                self.project_id = project
                return f"projects/{project}"
            raise ValueError(
                "No scope provided. Set project_id, organization_id, or folder_id, "
                "or set GOOGLE_CLOUD_PROJECT environment variable."
            )

    def validate_permissions(self) -> bool:
        """
        Check if required permissions are available.
        
        Returns:
            True if permissions are available, False otherwise.
        """
        try:
            client = self._get_client()
            scope = self._get_scope()

            # Try a simple asset search to verify access
            from google.cloud import asset_v1

            request = asset_v1.SearchAllResourcesRequest(
                scope=scope,
                page_size=1
            )

            # Just try to get one result to verify permissions
            results = client.search_all_resources(request)
            next(iter(results), None)  # Get first result or None

            logger.info("GCP permissions validated for scope: %s", scope)
            return True

        except Exception as e:
            logger.error("Permission validation failed: %s", e)
            return False

    def get_account_id(self) -> str:
        """
        Get the current project/org/folder identifier.
        
        Returns:
            Scope identifier string.
        """
        return self._get_scope()

    def collect(self) -> List[Dict]:
        """
        Collect GCP resources using Cloud Asset Inventory.
        
        Returns:
            List of inventory records with resource counts.
        """
        logger.info("Starting GCP resource collection via Cloud Asset Inventory")

        client = self._get_client()
        scope = self._get_scope()

        from google.cloud import asset_v1

        # Search all resources
        request = asset_v1.SearchAllResourcesRequest(
            scope=scope,
            page_size=500  # Max page size
        )

        # Count resources by type and location
        resource_counts = {}

        try:
            for resource in client.search_all_resources(request):
                # Extract resource type from asset_type
                # Format: servicename.googleapis.com/ResourceType
                asset_type = resource.asset_type

                # Extract project ID from name
                # Format: //servicename.googleapis.com/projects/PROJECT_ID/...
                name = resource.name
                project = self._extract_project_from_name(name)

                # Get location
                location = resource.location or 'global'

                key = (asset_type, project, location)
                resource_counts[key] = resource_counts.get(key, 0) + 1

        except Exception as e:
            logger.error("Error during resource collection: %s", e)

        # Convert counts to inventory records
        inventory = []
        for (asset_type, project, location), count in resource_counts.items():
            record = self.create_inventory_record(
                account_id=project or scope,
                region=location,
                resource_type=asset_type,
                count=count
            )
            inventory.append(record)

        self._inventory = inventory
        logger.info("Collected %d inventory records from GCP", len(inventory))

        return inventory

    def _extract_project_from_name(self, name: str) -> Optional[str]:
        """
        Extract project ID from resource name.
        
        Args:
            name: Resource name (e.g., //compute.googleapis.com/projects/my-project/...)
            
        Returns:
            Project ID or None if not found.
        """
        if '/projects/' in name:
            parts = name.split('/projects/')
            if len(parts) > 1:
                project_part = parts[1].split('/')[0]
                return project_part
        return None


def collect_gcp(
    project_id: str = None,
    organization_id: str = None,
    folder_id: str = None,
    resource_mappings: Dict = None,
    output_path: str = None
) -> List[Dict]:
    """
    Convenience function to collect GCP resources.
    
    Args:
        project_id: GCP project ID.
        organization_id: GCP organization ID.
        folder_id: GCP folder ID.
        resource_mappings: Optional resource type mappings.
        output_path: Optional path to save inventory JSON.
        
    Returns:
        List of inventory records.
    """
    collector = GCPCollector(
        resource_mappings=resource_mappings,
        project_id=project_id,
        organization_id=organization_id,
        folder_id=folder_id
    )

    if not collector.validate_permissions():
        raise PermissionError(
            "GCP permission validation failed. "
            "Ensure you have the Cloud Asset Viewer role."
        )

    inventory = collector.collect()

    if output_path:
        collector.save_inventory(output_path, inventory)

    collector.print_summary(inventory)

    return inventory

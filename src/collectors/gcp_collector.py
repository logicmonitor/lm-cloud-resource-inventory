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
        project_id: str = None,
        organization_id: str = None,
        folder_id: str = None
    ):
        """
        Initialize the GCP collector.
        
        Args:
            project_id: GCP project ID to query (for project-scoped collection).
            organization_id: GCP organization ID (for org-wide collection).
            folder_id: GCP folder ID (for folder-scoped collection).
        """
        super().__init__()
        self.project_id = project_id
        self.organization_id = organization_id
        self.folder_id = folder_id
        self._client = None
        self._errors_encountered = False

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
            import os
            import json

            project = os.environ.get('GOOGLE_CLOUD_PROJECT') or os.environ.get('GCLOUD_PROJECT')

            if not project:
                creds_file = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
                if creds_file and os.path.exists(creds_file):
                    try:
                        with open(creds_file, 'r', encoding='utf-8') as f:
                            creds = json.load(f)
                            project = creds.get('project_id')
                            if project:
                                logger.info(
                                    "Using project_id from credentials file: %s", project
                                )
                    except (json.JSONDecodeError, IOError):
                        pass

            if project:
                self.project_id = project
                return f"projects/{project}"

            raise ValueError(
                "No scope provided. Set project_id, organization_id, or folder_id, "
                "or set GOOGLE_CLOUD_PROJECT environment variable, "
                "or ensure GOOGLE_APPLICATION_CREDENTIALS points to a valid service account file."
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

            if self.organization_id:
                logger.info("Scope: Organization %s", self.organization_id)
            elif self.folder_id:
                logger.info("Scope: Folder %s", self.folder_id)
            elif self.project_id:
                logger.info("Scope: Project %s", self.project_id)

            from google.cloud import asset_v1

            request = asset_v1.SearchAllResourcesRequest(
                scope=scope,
                page_size=1
            )

            results = client.search_all_resources(request)
            next(iter(results), None)

            logger.info("GCP permissions validated successfully")
            return True

        except ImportError:
            raise
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

        request = asset_v1.SearchAllResourcesRequest(
            scope=scope,
            page_size=500
        )

        resource_counts = {}
        total_resources = 0
        projects_seen = set()

        try:
            logger.info("Scanning resources...")
            for resource in client.search_all_resources(request):
                asset_type = resource.asset_type

                name = resource.name
                project = self._extract_project_from_name(name)
                if project:
                    projects_seen.add(project)

                location = resource.location or 'global'

                key = (asset_type, project, location)
                resource_counts[key] = resource_counts.get(key, 0) + 1
                total_resources += 1

                if total_resources > 0 and total_resources % 5000 == 0:
                    logger.info("Scanned %d resources so far...", total_resources)

            if projects_seen:
                logger.info("Scanned %d resources across %d projects",
                            total_resources, len(projects_seen))

        except Exception as e:
            logger.error("Error during resource collection: %s", e)
            self._errors_encountered = True

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

        if self._errors_encountered:
            logger.warning(
                "Errors occurred during collection. Results may be incomplete. "
                "Re-run with --verbose for details."
            )

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
    output_path: str = None
) -> List[Dict]:
    """
    Convenience function to collect GCP resources.
    
    Args:
        project_id: GCP project ID.
        organization_id: GCP organization ID.
        folder_id: GCP folder ID.
        output_path: Optional path to save inventory JSON.
        
    Returns:
        List of inventory records.
    """
    collector = GCPCollector(
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

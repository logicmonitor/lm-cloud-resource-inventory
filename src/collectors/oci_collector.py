"""OCI Search Service collector for resource inventory."""

import logging
from typing import Dict, List, Optional

from .base import BaseCollector, require_import, retry_api_call

logger = logging.getLogger(__name__)


class OCICollector(BaseCollector):
    """
    OCI resource collector using OCI Search Service.
    
    The Search Service provides structured queries for discovering
    resources across compartments in a tenancy.
    """

    PROVIDER = "oci"

    # Only collect resource types that LM supports (matches resource_mappings.json)
    SUPPORTED_RESOURCE_TYPES = [
        "instance",
        "autonomousdatabase",
        "volume",
        "bootvolume",
        "volumereplica",
        "bucket",
        "drg",
    ]

    def __init__(
        self,
        compartment_id: Optional[str] = None,
        tenancy_id: Optional[str] = None,
        config_file: Optional[str] = None,
        config_profile: str = "DEFAULT",
    ):
        """
        Initialize the OCI collector.
        
        Args:
            compartment_id: OCI compartment OCID to query.
            tenancy_id: OCI tenancy OCID (for tenancy-wide collection).
            config_file: Path to OCI config file (default: ~/.oci/config).
            config_profile: OCI config profile name.
        """
        super().__init__()
        self.compartment_id = compartment_id
        self.tenancy_id = tenancy_id
        self.config_file = config_file
        self.config_profile = config_profile
        self._config = None
        self._search_client = None
        self._identity_client = None
        self._errors_encountered = False

    def _get_config(self):
        """Load OCI configuration."""
        if self._config is None:
            oci = require_import('oci', 'oci', 'oci')

            if self.config_file:
                self._config = oci.config.from_file(
                    file_location=self.config_file,
                    profile_name=self.config_profile
                )
            else:
                self._config = oci.config.from_file(
                    profile_name=self.config_profile
                )

        return self._config

    def _get_search_client(self):
        """Get OCI Search Service client."""
        if self._search_client is None:
            oci = require_import('oci', 'oci', 'oci')
            config = self._get_config()
            self._search_client = oci.resource_search.ResourceSearchClient(config)
        return self._search_client

    def _get_identity_client(self):
        """Get OCI Identity client."""
        if self._identity_client is None:
            oci = require_import('oci', 'oci', 'oci')
            config = self._get_config()
            self._identity_client = oci.identity.IdentityClient(config)
        return self._identity_client

    def _get_tenancy_id(self) -> str:
        """Get the tenancy OCID from config."""
        if self.tenancy_id:
            return self.tenancy_id
        config = self._get_config()
        return config.get('tenancy')

    def _get_root_compartment(self) -> str:
        """Get the root compartment (tenancy) ID."""
        return self.compartment_id or self._get_tenancy_id()

    def validate_permissions(self) -> bool:
        """
        Check if required permissions are available.
        
        Returns:
            True if permissions are available, False otherwise.
        """
        try:
            oci = require_import('oci', 'oci', 'oci')

            logger.info("Using OCI config profile: %s", self.config_profile)

            search_client = self._get_search_client()
            compartment = self._get_root_compartment()

            tenancy_id = self._get_tenancy_id()
            logger.info("Tenancy: %s", tenancy_id)

            search_details = oci.resource_search.models.StructuredSearchDetails(
                query=f"query all resources where compartmentId = '{compartment}'",
                type="Structured"
            )

            search_client.search_resources(search_details, limit=1)

            logger.info("OCI permissions validated successfully")
            return True

        except ImportError:
            raise
        except Exception as e:
            logger.error("Permission validation failed: %s", e)
            return False

    def get_account_id(self) -> str:
        """
        Get the current tenancy/compartment identifier.
        
        Returns:
            Tenancy or compartment OCID.
        """
        return self._get_root_compartment()

    def _get_all_compartments(self, parent_compartment_id: str) -> List[str]:
        """
        Recursively get all compartment OCIDs with full pagination.
        
        Args:
            parent_compartment_id: Parent compartment OCID.
            
        Returns:
            List of compartment OCIDs including parent.
        """
        oci = require_import('oci', 'oci', 'oci')

        identity_client = self._get_identity_client()
        compartments = [parent_compartment_id]

        try:
            all_compartments = oci.pagination.list_call_get_all_results(
                identity_client.list_compartments,
                compartment_id=parent_compartment_id,
                compartment_id_in_subtree=True,
                lifecycle_state="ACTIVE"
            )

            for compartment in all_compartments.data:
                compartments.append(compartment.id)

        except Exception as e:
            logger.warning("Failed to list compartments: %s", e)
            self._errors_encountered = True

        return compartments

    def _search_resource_type(self, search_client, oci_module,
                              resource_type: str, compartment_id: str,
                              resource_counts: Dict) -> int:
        """Search a single resource type in one compartment and update counts."""
        query = (
            f"query {resource_type} resources "
            f"where compartmentId = '{compartment_id}'"
        )
        search_details = oci_module.resource_search.models.StructuredSearchDetails(
            query=query, type="Structured"
        )

        page = None
        count = 0

        while True:
            if page:
                response = retry_api_call(
                    search_client.search_resources, search_details, page=page
                )
            else:
                response = retry_api_call(
                    search_client.search_resources, search_details
                )

            for item in (response.data.items or []):
                region = getattr(item, 'region', None) or 'regional'
                key = (resource_type, compartment_id, region)
                resource_counts[key] = resource_counts.get(key, 0) + 1
                count += 1

            if response.has_next_page:
                page = response.next_page
            else:
                break

        return count

    def collect(self) -> List[Dict]:
        """
        Collect OCI resources using Search Service.

        Returns:
            List of inventory records with resource counts.
        """
        logger.info("Starting OCI resource collection via Search Service")
        self._errors_encountered = False

        oci = require_import('oci', 'oci', 'oci')

        search_client = self._get_search_client()
        root_compartment = self._get_root_compartment()

        logger.info("Root compartment: %s", root_compartment)
        compartments = self._get_all_compartments(root_compartment)
        logger.info(
            "Discovered %d compartments to search (%d child compartments)",
            len(compartments), len(compartments) - 1
        )

        resource_counts: Dict = {}
        total_compartments = len(compartments)

        for comp_idx, compartment_id in enumerate(compartments, 1):
            if total_compartments > 5 and comp_idx % 5 == 0:
                logger.info("Scanning compartment %d/%d...", comp_idx, total_compartments)

            for resource_type in self.SUPPORTED_RESOURCE_TYPES:
                try:
                    count = self._search_resource_type(
                        search_client, oci, resource_type,
                        compartment_id, resource_counts
                    )
                    if count > 0:
                        logger.debug("Found %d %s in compartment %s",
                                     count, resource_type, compartment_id)
                except Exception as e:
                    logger.warning("Error querying %s in compartment %s: %s",
                                   resource_type, compartment_id, e)
                    self._errors_encountered = True

        inventory = []

        aggregated = {}
        tenancy = self._get_tenancy_id()

        for (resource_type, _, region), count in resource_counts.items():
            key = (resource_type, region)
            aggregated[key] = aggregated.get(key, 0) + count

        for (resource_type, region), count in aggregated.items():
            record = self.create_inventory_record(
                account_id=tenancy,
                region=region,
                resource_type=resource_type,
                count=count
            )
            inventory.append(record)

        self._inventory = inventory
        logger.info("Collected %d inventory records from OCI", len(inventory))

        if self._errors_encountered:
            logger.warning(
                "Some queries encountered errors. Results may be incomplete. "
                "Re-run with --verbose for details."
            )

        return inventory


def collect_oci(
    compartment_id: Optional[str] = None,
    tenancy_id: Optional[str] = None,
    config_file: Optional[str] = None,
    config_profile: str = "DEFAULT",
    output_path: Optional[str] = None,
) -> List[Dict]:
    """
    Convenience function to collect OCI resources.
    
    Args:
        compartment_id: OCI compartment OCID.
        tenancy_id: OCI tenancy OCID.
        config_file: Path to OCI config file.
        config_profile: OCI config profile name.
        output_path: Optional path to save inventory JSON.
        
    Returns:
        List of inventory records.
    """
    collector = OCICollector(
        compartment_id=compartment_id,
        tenancy_id=tenancy_id,
        config_file=config_file,
        config_profile=config_profile
    )

    if not collector.validate_permissions():
        raise PermissionError(
            "OCI permission validation failed. "
            "Ensure you have inspect permissions on all-resources."
        )

    inventory = collector.collect()

    if output_path:
        collector.save_inventory(output_path, inventory)

    collector.print_summary(inventory)

    return inventory

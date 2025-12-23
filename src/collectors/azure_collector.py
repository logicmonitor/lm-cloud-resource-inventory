"""Azure Resource Graph collector for resource inventory."""

import logging
from typing import Dict, List

from .base import BaseCollector

logger = logging.getLogger(__name__)


class AzureCollector(BaseCollector):
    """
    Azure resource collector using Azure Resource Graph.
    
    Azure Resource Graph provides fast, efficient resource querying
    across all subscriptions using KQL (Kusto Query Language).
    """

    PROVIDER = "azure"

    def __init__(
        self,
        resource_mappings: Dict = None,
        subscription_ids: List[str] = None,
        management_group_id: str = None
    ):
        """
        Initialize the Azure collector.
        
        Args:
            resource_mappings: Optional dict mapping resource types to categories.
            subscription_ids: Optional list of subscription IDs to query.
                            If not provided, queries all accessible subscriptions.
            management_group_id: Optional management group ID for scope.
        """
        super().__init__(resource_mappings)
        self.subscription_ids = subscription_ids
        self.management_group_id = management_group_id
        self._credential = None
        self._graph_client = None
        self._resource_client = None
        self._subscription_info: List[Dict] = []  # List of {id, name} dicts

    def _get_credential(self):
        """Get Azure credential using DefaultAzureCredential."""
        if self._credential is None:
            try:
                from azure.identity import DefaultAzureCredential
                self._credential = DefaultAzureCredential()
            except ImportError as exc:
                raise ImportError(
                    "azure-identity package is required. "
                    "Install with: pip install azure-identity"
                ) from exc
        return self._credential

    def _get_graph_client(self):
        """Get Azure Resource Graph client."""
        if self._graph_client is None:
            try:
                from azure.mgmt.resourcegraph import ResourceGraphClient
                self._graph_client = ResourceGraphClient(self._get_credential())
            except ImportError as exc:
                raise ImportError(
                    "azure-mgmt-resourcegraph package is required. "
                    "Install with: pip install azure-mgmt-resourcegraph"
                ) from exc
        return self._graph_client

    def _get_subscriptions(self) -> List[str]:
        """
        Get list of subscription IDs to query.
        
        Returns:
            List of subscription ID strings.
        """
        if self.subscription_ids:
            return self.subscription_ids

        # Get all accessible subscriptions with names
        try:
            from azure.mgmt.resource import SubscriptionClient
            sub_client = SubscriptionClient(self._get_credential())
            subscriptions = []
            self._subscription_info = []

            for sub in sub_client.subscriptions.list():
                if sub.state == "Enabled":
                    subscriptions.append(sub.subscription_id)
                    self._subscription_info.append({
                        'id': sub.subscription_id,
                        'name': sub.display_name or sub.subscription_id
                    })

            # Log subscriptions with names
            if self._subscription_info:
                sub_names = [s['name'] for s in self._subscription_info]
                if len(sub_names) <= 5:
                    logger.info("Found %d subscriptions: %s",
                                len(subscriptions), ", ".join(sub_names))
                else:
                    logger.info("Found %d subscriptions: %s, and %d more",
                                len(subscriptions), ", ".join(sub_names[:5]), len(sub_names) - 5)

            return subscriptions
        except ImportError as exc:
            raise ImportError(
                "azure-mgmt-resource package is required. "
                "Install with: pip install azure-mgmt-resource"
            ) from exc

    def validate_permissions(self) -> bool:
        """
        Check if required permissions are available.
        
        Returns:
            True if permissions are available, False otherwise.
        """
        try:
            # Get credential and log auth method
            credential = self._get_credential()
            # The credential type name indicates the auth method
            cred_type = type(credential).__name__
            logger.info("Authenticating via: %s", cred_type)

            # Try to list subscriptions to verify access
            subscriptions = self._get_subscriptions()
            if not subscriptions:
                logger.warning("No accessible subscriptions found")
                return False

            # Try a simple Resource Graph query
            client = self._get_graph_client()
            from azure.mgmt.resourcegraph.models import QueryRequest
            query = QueryRequest(
                subscriptions=subscriptions[:1],  # Just test with first subscription
                query="Resources | take 1"
            )
            client.resources(query)
            logger.info("Azure permissions validated successfully")
            return True

        except Exception as e:
            logger.error("Permission validation failed: %s", e)
            return False

    def get_account_id(self) -> str:
        """
        Get the current subscription context.
        
        For Azure, this returns a comma-separated list of subscription IDs
        or 'all' if querying all subscriptions.
        
        Returns:
            String identifier for the subscription context.
        """
        subs = self._get_subscriptions()
        if len(subs) == 1:
            return subs[0]
        return f"{len(subs)}_subscriptions"

    def collect(self) -> List[Dict]:
        """
        Collect Azure resources using Resource Graph.
        
        Returns:
            List of inventory records with resource counts by type and location.
        """
        logger.info("Starting Azure resource collection via Resource Graph")

        subscriptions = self._get_subscriptions()
        if not subscriptions:
            logger.warning("No subscriptions to query")
            return []

        client = self._get_graph_client()

        # Resource Graph query to count resources by type, subscription, and location
        query_str = """
        Resources
        | summarize count() by type, subscriptionId, location
        | order by count_ desc
        """

        from azure.mgmt.resourcegraph.models import QueryRequest

        inventory = []

        # Process in batches of 200 subscriptions (Resource Graph limit)
        batch_size = 200
        total_batches = (len(subscriptions) + batch_size - 1) // batch_size

        for i in range(0, len(subscriptions), batch_size):
            batch = subscriptions[i:i + batch_size]
            batch_num = i // batch_size + 1
            if total_batches > 1:
                logger.info("Querying batch %d of %d (%d subscriptions)",
                            batch_num, total_batches, len(batch))

            query = QueryRequest(
                subscriptions=batch,
                query=query_str
            )

            try:
                result = client.resources(query)

                for row in result.data:
                    resource_type = row.get('type', '').lower()
                    subscription_id = row.get('subscriptionId', '')
                    location = row.get('location', 'global')
                    count = row.get('count_', 0)

                    record = self.create_inventory_record(
                        account_id=subscription_id,
                        region=location,
                        resource_type=resource_type,
                        count=count
                    )
                    inventory.append(record)

            except Exception as e:
                logger.error("Error querying batch: %s", e)
                continue

        # Also get VMSS instances (requires separate query)
        vmss_inventory = self._collect_vmss_instances(subscriptions)
        inventory.extend(vmss_inventory)

        self._inventory = inventory
        logger.info("Collected %d inventory records from Azure", len(inventory))

        return inventory

    def _collect_vmss_instances(self, subscriptions: List[str]) -> List[Dict]:
        """
        Collect Virtual Machine Scale Set instances.
        
        VMSS instances are counted separately as IaaS resources.
        
        Args:
            subscriptions: List of subscription IDs to query.
            
        Returns:
            List of inventory records for VMSS instances.
        """
        client = self._get_graph_client()

        # Query for VMSS instance count
        query_str = """
        ComputeResources
        | where type == 'microsoft.compute/virtualmachinescalesets/virtualmachines'
        | summarize count() by subscriptionId, location
        """

        from azure.mgmt.resourcegraph.models import QueryRequest

        inventory = []
        batch_size = 200

        for i in range(0, len(subscriptions), batch_size):
            batch = subscriptions[i:i + batch_size]

            query = QueryRequest(
                subscriptions=batch,
                query=query_str
            )

            try:
                result = client.resources(query)

                for row in result.data:
                    subscription_id = row.get('subscriptionId', '')
                    location = row.get('location', 'global')
                    count = row.get('count_', 0)

                    if count > 0:
                        record = self.create_inventory_record(
                            account_id=subscription_id,
                            region=location,
                            resource_type='microsoft.compute/virtualmachinescalesets/virtualmachines',
                            count=count
                        )
                        inventory.append(record)

            except Exception as e:
                # VMSS instances query may fail on some subscriptions
                logger.debug("VMSS query failed for batch: %s", e)
                continue

        return inventory


def collect_azure(
    subscriptions: List[str] = None,
    resource_mappings: Dict = None,
    output_path: str = None
) -> List[Dict]:
    """
    Convenience function to collect Azure resources.
    
    Args:
        subscriptions: Optional list of subscription IDs.
        resource_mappings: Optional resource type mappings.
        output_path: Optional path to save inventory JSON.
        
    Returns:
        List of inventory records.
    """
    collector = AzureCollector(
        resource_mappings=resource_mappings,
        subscription_ids=subscriptions
    )

    if not collector.validate_permissions():
        raise PermissionError(
            "Azure permission validation failed. "
            "Ensure you have Reader access to the subscriptions."
        )

    inventory = collector.collect()

    if output_path:
        collector.save_inventory(output_path, inventory)

    collector.print_summary(inventory)

    return inventory

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
        subscription_ids: List[str] = None,
        management_group_id: str = None
    ):
        """
        Initialize the Azure collector.
        
        Args:
            subscription_ids: Optional list of subscription IDs to query.
                            If not provided, queries all accessible subscriptions.
            management_group_id: Optional management group ID for scope.
        """
        super().__init__()
        self.subscription_ids = subscription_ids
        self.management_group_id = management_group_id
        self._credential = None
        self._graph_client = None
        self._resource_client = None
        self._subscription_info: List[Dict] = []
        self._errors_encountered = False

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
        Results are cached after first discovery.
        
        Returns:
            List of subscription ID strings.
        """
        if self.subscription_ids:
            return self.subscription_ids

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

            if self._subscription_info:
                sub_names = [s['name'] for s in self._subscription_info]
                if len(sub_names) <= 5:
                    logger.info("Found %d subscriptions: %s",
                                len(subscriptions), ", ".join(sub_names))
                else:
                    logger.info("Found %d subscriptions: %s, and %d more",
                                len(subscriptions), ", ".join(sub_names[:5]), len(sub_names) - 5)

            # Cache the discovered subscriptions to avoid redundant API calls
            self.subscription_ids = subscriptions
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
            credential = self._get_credential()
            cred_type = type(credential).__name__
            logger.info("Authenticating via: %s", cred_type)

            subscriptions = self._get_subscriptions()
            if not subscriptions:
                logger.warning("No accessible subscriptions found")
                return False

            client = self._get_graph_client()
            from azure.mgmt.resourcegraph.models import QueryRequest
            query = QueryRequest(
                subscriptions=subscriptions[:1],
                query="Resources | take 1"
            )
            client.resources(query)
            logger.info("Azure permissions validated successfully")
            return True

        except ImportError:
            raise
        except Exception as e:
            logger.error("Permission validation failed: %s", e)
            return False

    def get_account_id(self) -> str:
        """
        Get the current subscription context.
        
        Returns:
            String identifier for the subscription context.
        """
        subs = self._get_subscriptions()
        if len(subs) == 1:
            return subs[0]
        return f"{len(subs)}_subscriptions"

    def _query_resource_graph(self, query_str: str, subscriptions: List[str]) -> List[Dict]:
        """
        Execute a Resource Graph query with full pagination support.
        
        Azure Resource Graph returns max 1000 rows per request. This method
        handles skip_token pagination to retrieve all results.
        
        Args:
            query_str: KQL query string.
            subscriptions: List of subscription IDs to query.
            
        Returns:
            List of result row dicts.
        """
        from azure.mgmt.resourcegraph.models import (
            QueryRequest, QueryRequestOptions
        )

        client = self._get_graph_client()
        all_rows = []
        batch_size = 200

        for i in range(0, len(subscriptions), batch_size):
            batch = subscriptions[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(subscriptions) + batch_size - 1) // batch_size

            if total_batches > 1:
                logger.info("Querying batch %d of %d (%d subscriptions)",
                            batch_num, total_batches, len(batch))

            skip_token = None
            page = 0

            while True:
                try:
                    options = QueryRequestOptions(
                        skip_token=skip_token
                    ) if skip_token else None

                    query = QueryRequest(
                        subscriptions=batch,
                        query=query_str,
                        options=options
                    )

                    result = client.resources(query)
                    rows = result.data or []
                    all_rows.extend(rows)

                    page += 1
                    if page > 1:
                        logger.info("  Fetched page %d (%d rows so far)", page, len(all_rows))

                    skip_token = result.skip_token
                    if not skip_token:
                        break

                except Exception as e:
                    logger.error("Error querying Resource Graph (batch %d, page %d): %s",
                                 batch_num, page + 1, e)
                    self._errors_encountered = True
                    break

        return all_rows

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

        query_str = """
        Resources
        | summarize count() by type, subscriptionId, location
        | order by count_ desc
        """

        rows = self._query_resource_graph(query_str, subscriptions)

        inventory = []
        for row in rows:
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

        vmss_inventory = self._collect_vmss_instances(subscriptions)
        inventory.extend(vmss_inventory)

        self._inventory = inventory
        logger.info("Collected %d inventory records from Azure", len(inventory))

        if self._errors_encountered:
            logger.warning(
                "Some queries encountered errors. Results may be incomplete. "
                "Re-run with --verbose for details."
            )

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
        query_str = """
        ComputeResources
        | where type == 'microsoft.compute/virtualmachinescalesets/virtualmachines'
        | summarize count() by subscriptionId, location
        """

        rows = self._query_resource_graph(query_str, subscriptions)

        inventory = []
        for row in rows:
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

        return inventory


def collect_azure(
    subscriptions: List[str] = None,
    output_path: str = None
) -> List[Dict]:
    """
    Convenience function to collect Azure resources.
    
    Args:
        subscriptions: Optional list of subscription IDs.
        output_path: Optional path to save inventory JSON.
        
    Returns:
        List of inventory records.
    """
    collector = AzureCollector(
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

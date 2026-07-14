"""AWS Resource Explorer collector for resource inventory."""

import logging
from typing import Dict, List, Optional

from .base import BaseCollector, require_import, retry_api_call

logger = logging.getLogger(__name__)

# Services NOT supported by AWS Resource Explorer (as of Dec 2024)
# These require manual inventory if used. See README.md for details.
# Reference: https://docs.aws.amazon.com/resource-explorer/latest/userguide/supported-resource-types.html
UNSUPPORTED_SERVICES = [
    "CloudSearch (Domain)",
    "MediaConnect (Flow)",
    "MediaConvert (Queue)",
    "OpsWorks (Stack)",
    "Q Business (Application)",
    "QuickSight (Dashboard only - dataset/datasource are supported)",
    "Simple Workflow SWF (Domain)",
    "Application Migration Service (Source Server)",
    "ElasticTranscoder (Pipeline)",
]


class AWSCollector(BaseCollector):
    """
    AWS resource collector using AWS Resource Explorer.
    
    AWS Resource Explorer provides fast, unified search across all regions
    and resource types in an AWS account or organization.
    
    Prerequisites:
    - Resource Explorer must be enabled in the account/organization
    - An aggregator index should be created for cross-region queries
    """

    PROVIDER = "aws"

    def __init__(
        self,
        profile_name: Optional[str] = None,
        region: str = "us-east-1",
        use_organizations: bool = False,
        organization_role: Optional[str] = None,
    ):
        """
        Initialize the AWS collector.
        
        Args:
            profile_name: AWS profile name to use for credentials.
            region: Region for Resource Explorer API calls (default: us-east-1).
            use_organizations: Whether to collect across all org accounts.
            organization_role: IAM role name to assume in member accounts.
        """
        super().__init__()
        self.profile_name = profile_name
        self.region = region
        self.use_organizations = use_organizations
        self.organization_role = organization_role
        self._session = None
        self._account_id = None
        self._aggregator_region = None
        self._local_index_regions = []
        self._errors_encountered = False

    def _get_session(self, profile_name: str = None, credentials: Dict = None):
        """Get boto3 session."""
        boto3 = require_import('boto3', 'boto3', 'aws')

        if credentials:
            return boto3.Session(
                aws_access_key_id=credentials['AccessKeyId'],
                aws_secret_access_key=credentials['SecretAccessKey'],
                aws_session_token=credentials.get('SessionToken'),
                region_name=self.region
            )
        elif profile_name or self.profile_name:
            return boto3.Session(
                profile_name=profile_name or self.profile_name,
                region_name=self.region
            )
        else:
            return boto3.Session(region_name=self.region)

    def _get_default_session(self):
        """Get the default boto3 session."""
        if self._session is None:
            self._session = self._get_session()
        return self._session

    def validate_permissions(self) -> bool:
        """
        Check if required permissions are available.
        
        Returns:
            True if permissions are available, False otherwise.
        """
        try:
            session = self._get_default_session()

            if self.profile_name:
                logger.info("Using AWS profile: %s", self.profile_name)

            sts = session.client('sts')
            identity = sts.get_caller_identity()
            self._account_id = identity['Account']
            logger.info("Authenticated as: %s", identity['Arn'])

            rex = session.client('resource-explorer-2')

            try:
                indexes = self._list_all_indexes(rex)
                if not indexes:
                    logger.error(
                        "AWS Resource Explorer is not enabled. "
                        "This tool requires Resource Explorer to collect resources. "
                        "Please enable it: https://docs.aws.amazon.com/resource-explorer/"
                    )
                    return False

                self._apply_index_topology(indexes)
                return True

            except rex.exceptions.AccessDeniedException:
                logger.error(
                    "No access to Resource Explorer. "
                    "Ensure the IAM policy includes resource-explorer-2:* permissions. "
                    "See: https://docs.aws.amazon.com/resource-explorer/"
                )
                return False

        except ImportError:
            raise
        except Exception as e:
            logger.error("Permission validation failed: %s", e)
            return False

    def _list_all_indexes(self, rex_client) -> List[Dict]:
        """List all Resource Explorer indexes with pagination."""
        indexes = []
        next_token = None

        while True:
            params = {}
            if next_token:
                params['NextToken'] = next_token

            response = rex_client.list_indexes(**params)
            indexes.extend(response.get('Indexes', []))

            next_token = response.get('NextToken')
            if not next_token:
                break

        return indexes

    @staticmethod
    def _parse_index_topology(indexes: List[Dict]) -> tuple:
        """
        Parse index list and return (aggregator_region, sorted_local_regions).

        Args:
            indexes: List of index dicts from list_indexes API.

        Returns:
            Tuple of (aggregator_region or None, sorted list of local regions).
        """
        aggregator_region = None
        local_regions = []

        for idx in indexes:
            idx_type = idx.get('Type', 'LOCAL')
            idx_region = idx.get('Region', '')
            if idx_type == 'AGGREGATOR':
                aggregator_region = idx_region
            else:
                local_regions.append(idx_region)

        return aggregator_region, sorted(local_regions)

    def _apply_index_topology(self, indexes: List[Dict]):
        """
        Parse index list and store aggregator/local region info.

        Args:
            indexes: List of index dicts from list_indexes API.
        """
        aggregator_region, local_regions = self._parse_index_topology(indexes)

        self._local_index_regions = local_regions

        if aggregator_region:
            logger.info(
                "Found Resource Explorer aggregator in %s",
                aggregator_region
            )
            logger.info(
                "Will query aggregator for all %d indexed regions",
                len(local_regions) + 1
            )
            self._aggregator_region = aggregator_region
        else:
            logger.info(
                "No aggregator index found - will query %d regional indexes",
                len(local_regions)
            )
            if local_regions:
                logger.info("Indexed regions: %s", ", ".join(local_regions))
            self._aggregator_region = None

    def get_account_id(self) -> str:
        """
        Get the current AWS account ID.
        
        Returns:
            AWS account ID string.
        """
        if self._account_id is None:
            session = self._get_default_session()
            sts = session.client('sts')
            self._account_id = sts.get_caller_identity()['Account']
        return self._account_id

    def _collect_via_resource_explorer(
        self, session, account_id: str,
        aggregator_region: str = None,
        local_index_regions: List[str] = None
    ) -> List[Dict]:
        """
        Collect resources using AWS Resource Explorer ListResources API.
        
        Uses the aggregator index if available for cross-region queries,
        otherwise queries each regional index individually.
        
        Args:
            session: boto3 session to use.
            account_id: AWS account ID for labeling records.
            aggregator_region: Region with the aggregator index, if any.
            local_index_regions: Regions with local indexes.
        """
        if aggregator_region:
            regions_to_query = [aggregator_region]
            logger.info("Querying aggregator index in %s", aggregator_region)
        elif local_index_regions:
            regions_to_query = local_index_regions
            logger.info("Querying %d regional indexes...", len(regions_to_query))
        else:
            regions_to_query = [self.region]
            logger.warning("No index information available, querying %s only", self.region)

        resource_counts = {}
        total_resources = 0
        regions_queried = 0

        try:
            for query_region in regions_to_query:
                regions_queried += 1

                if len(regions_to_query) > 1:
                    logger.info(
                        "Querying region %d/%d: %s",
                        regions_queried, len(regions_to_query), query_region
                    )

                rex = session.client('resource-explorer-2', region_name=query_region)

                next_token = None

                while True:
                    params = {'MaxResults': 500}
                    if next_token:
                        params['NextToken'] = next_token

                    response = retry_api_call(rex.list_resources, **params)

                    for resource in response.get('Resources', []):
                        resource_type = resource.get('ResourceType', '')
                        region = resource.get('Region', 'global')

                        key = (resource_type, region)
                        resource_counts[key] = resource_counts.get(key, 0) + 1
                        total_resources += 1

                    if total_resources > 0 and total_resources % 5000 == 0:
                        logger.info("Scanned %d resources so far...", total_resources)

                    next_token = response.get('NextToken')
                    if not next_token:
                        break

            unique_regions = set(r for (_, r) in resource_counts)
            logger.info(
                "Scanned %d resources across %d regions",
                total_resources, len(unique_regions)
            )

            inventory = []
            for (resource_type, region), count in resource_counts.items():
                record = self.create_inventory_record(
                    account_id=account_id,
                    region=region,
                    resource_type=resource_type,
                    count=count
                )
                inventory.append(record)

            return inventory

        except Exception as e:
            logger.error("Resource Explorer list_resources failed: %s", e)
            self._errors_encountered = True
            return []

    def _get_org_accounts(self) -> List[Dict]:
        """Get all accounts in the organization."""
        session = self._get_default_session()
        org = session.client('organizations')

        accounts = []
        paginator = org.get_paginator('list_accounts')

        for page in paginator.paginate():
            for account in page.get('Accounts', []):
                if account['Status'] == 'ACTIVE':
                    accounts.append({
                        'Id': account['Id'],
                        'Name': account['Name']
                    })

        return accounts

    def _assume_role(self, account_id: str, role_name: str) -> Optional[Dict]:
        """Assume role in a member account."""
        session = self._get_default_session()
        sts = session.client('sts')

        role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"

        try:
            response = sts.assume_role(
                RoleArn=role_arn,
                RoleSessionName='LMInventorySession'
            )
            return response['Credentials']
        except Exception as e:
            logger.warning("Failed to assume role in account %s: %s", account_id, e)
            return None

    def _discover_account_indexes(self, session) -> tuple:
        """
        Discover Resource Explorer index topology for an account.

        Returns:
            Tuple of (aggregator_region, local_index_regions) or (None, [])
            if Resource Explorer is not enabled.
        """
        try:
            rex = session.client('resource-explorer-2', region_name=self.region)
            indexes = self._list_all_indexes(rex)

            if not indexes:
                return None, []

            return self._parse_index_topology(indexes)

        except Exception as e:
            logger.warning("Failed to discover indexes: %s", e)
            return None, []

    def collect(self) -> List[Dict]:
        """
        Collect AWS resources.
        
        Returns:
            List of inventory records.
        """
        logger.info("Starting AWS resource collection")
        self._errors_encountered = False

        all_inventory = []

        if self.use_organizations and self.organization_role:
            accounts = self._get_org_accounts()
            logger.info("Collecting from %d organization accounts", len(accounts))

            for account in accounts:
                account_id = account['Id']
                account_name = account['Name']
                logger.info("Processing account: %s (%s)", account_name, account_id)

                if account_id == self.get_account_id():
                    session = self._get_default_session()
                    agg_region = self._aggregator_region
                    local_regions = self._local_index_regions
                else:
                    credentials = self._assume_role(account_id, self.organization_role)
                    if not credentials:
                        self._errors_encountered = True
                        continue
                    session = self._get_session(credentials=credentials)

                    agg_region, local_regions = self._discover_account_indexes(session)
                    if not agg_region and not local_regions:
                        logger.warning(
                            "Resource Explorer not enabled in account %s (%s) - skipping",
                            account_name, account_id
                        )
                        continue

                inventory = self._collect_via_resource_explorer(
                    session, account_id,
                    aggregator_region=agg_region,
                    local_index_regions=local_regions
                )
                all_inventory.extend(inventory)
        else:
            session = self._get_default_session()
            account_id = self.get_account_id()
            logger.info("Collecting from account: %s", account_id)
            all_inventory = self._collect_via_resource_explorer(
                session, account_id,
                aggregator_region=self._aggregator_region,
                local_index_regions=self._local_index_regions
            )

        self._inventory = all_inventory
        logger.info("Collected %d inventory records from AWS", len(all_inventory))

        if self._errors_encountered:
            logger.warning(
                "Some accounts/regions encountered errors. Results may be incomplete. "
                "Re-run with --verbose for details."
            )

        return all_inventory


def collect_aws(
    profile: Optional[str] = None,
    region: str = "us-east-1",
    use_organizations: bool = False,
    organization_role: Optional[str] = None,
    output_path: Optional[str] = None,
) -> List[Dict]:
    """
    Convenience function to collect AWS resources.
    
    Args:
        profile: AWS profile name.
        region: AWS region for API calls.
        use_organizations: Whether to collect across org accounts.
        organization_role: IAM role to assume in member accounts.
        output_path: Optional path to save inventory JSON.
        
    Returns:
        List of inventory records.
    """
    collector = AWSCollector(
        profile_name=profile,
        region=region,
        use_organizations=use_organizations,
        organization_role=organization_role
    )

    if not collector.validate_permissions():
        raise PermissionError(
            "AWS permission validation failed. "
            "Ensure you have the required IAM permissions."
        )

    inventory = collector.collect()

    if output_path:
        collector.save_inventory(output_path, inventory)

    collector.print_summary(inventory)

    return inventory

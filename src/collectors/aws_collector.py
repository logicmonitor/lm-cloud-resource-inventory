"""AWS Resource Explorer collector for resource inventory."""

import logging
from typing import Dict, List, Optional

from .base import BaseCollector

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
        resource_mappings: Dict = None,
        profile_name: str = None,
        region: str = "us-east-1",
        use_organizations: bool = False,
        organization_role: str = None
    ):
        """
        Initialize the AWS collector.
        
        Args:
            resource_mappings: Optional dict mapping resource types to categories.
            profile_name: AWS profile name to use for credentials.
            region: Region for Resource Explorer API calls (default: us-east-1).
            use_organizations: Whether to collect across all org accounts.
            organization_role: IAM role name to assume in member accounts.
        """
        super().__init__(resource_mappings)
        self.profile_name = profile_name
        self.region = region
        self.use_organizations = use_organizations
        self.organization_role = organization_role
        self._session = None
        self._account_id = None
        self._aggregator_region = None
        self._local_index_regions = []

    def _get_session(self, profile_name: str = None, credentials: Dict = None):
        """Get boto3 session."""
        try:
            import boto3

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

        except ImportError as exc:
            raise ImportError(
                "boto3 package is required. "
                "Install with: pip install boto3"
            ) from exc

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

            # Log profile being used
            if self.profile_name:
                logger.info("Using AWS profile: %s", self.profile_name)

            # Verify identity
            sts = session.client('sts')
            identity = sts.get_caller_identity()
            self._account_id = identity['Account']
            logger.info("Authenticated as: %s", identity['Arn'])

            # Check if Resource Explorer is available (required)
            rex = session.client('resource-explorer-2')

            try:
                # Try to list indexes to verify Resource Explorer is enabled
                indexes = rex.list_indexes()
                if not indexes.get('Indexes'):
                    logger.error(
                        "AWS Resource Explorer is not enabled. "
                        "This tool requires Resource Explorer to collect resources. "
                        "Please enable it: https://docs.aws.amazon.com/resource-explorer/"
                    )
                    return False

                # Find the aggregator index for cross-region queries
                aggregator_region = None
                local_regions = []
                for idx in indexes.get('Indexes', []):
                    idx_type = idx.get('Type', 'LOCAL')
                    idx_region = idx.get('Region', '')
                    if idx_type == 'AGGREGATOR':
                        aggregator_region = idx_region
                    else:
                        local_regions.append(idx_region)

                # Store for use during collection
                self._local_index_regions = sorted(local_regions)

                if aggregator_region:
                    logger.info(
                        "Found Resource Explorer aggregator in %s",
                        aggregator_region
                    )
                    logger.info(
                        "Will query aggregator for all %d indexed regions",
                        len(local_regions) + 1  # aggregator region is also indexed
                    )
                    self._aggregator_region = aggregator_region
                else:
                    logger.info(
                        "No aggregator index found - will query %d regional indexes",
                        len(local_regions)
                    )
                    if local_regions:
                        logger.info("Indexed regions: %s", ", ".join(sorted(local_regions)))
                    self._aggregator_region = None

                return True

            except rex.exceptions.AccessDeniedException:
                logger.error(
                    "No access to Resource Explorer. "
                    "Ensure the IAM policy includes resource-explorer-2:* permissions. "
                    "See: https://docs.aws.amazon.com/resource-explorer/"
                )
                return False

        except Exception as e:
            logger.error("Permission validation failed: %s", e)
            return False

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

    def _collect_via_resource_explorer(self, session, account_id: str) -> List[Dict]:
        """
        Collect resources using AWS Resource Explorer ListResources API.
        
        Uses the aggregator index if available for cross-region queries,
        otherwise queries each regional index individually.
        
        Note: We use ListResources instead of Search because the Search API
        has a hard limit of 1000 results. ListResources supports true pagination.
        See: https://docs.aws.amazon.com/resource-explorer/latest/apireference/API_ListResources.html
        """
        # Determine which regions to query
        if self._aggregator_region:
            # Single query to aggregator gets all regions
            regions_to_query = [self._aggregator_region]
            logger.info("Querying aggregator index in %s", self._aggregator_region)
        elif self._local_index_regions:
            # No aggregator - query each regional index
            regions_to_query = self._local_index_regions
            logger.info("Querying %d regional indexes...", len(regions_to_query))
        else:
            # Fallback to configured region only
            regions_to_query = [self.region]
            logger.warning("No index information available, querying %s only", self.region)

        # Count resources by type and region
        resource_counts = {}
        total_resources = 0
        regions_queried = 0

        try:
            for query_region in regions_to_query:
                regions_queried += 1

                # Log progress when querying multiple regions
                if len(regions_to_query) > 1:
                    logger.info(
                        "Querying region %d/%d: %s",
                        regions_queried, len(regions_to_query), query_region
                    )

                rex = session.client('resource-explorer-2', region_name=query_region)

                # Use ListResources API with pagination (no 1000 result limit)
                # MaxResults must be < 1000 to ensure NextToken is returned
                next_token = None

                while True:
                    params = {'MaxResults': 500}
                    if next_token:
                        params['NextToken'] = next_token

                    response = rex.list_resources(**params)

                    for resource in response.get('Resources', []):
                        resource_type = resource.get('ResourceType', '')
                        region = resource.get('Region', 'global')

                        key = (resource_type, region)
                        resource_counts[key] = resource_counts.get(key, 0) + 1
                        total_resources += 1

                    # Log progress for large inventories
                    if total_resources > 0 and total_resources % 5000 == 0:
                        logger.info("Scanned %d resources so far...", total_resources)

                    next_token = response.get('NextToken')
                    if not next_token:
                        break

            # Summary log
            unique_regions = set(r for (_, r) in resource_counts)
            logger.info(
                "Scanned %d resources across %d regions",
                total_resources, len(unique_regions)
            )

            # Convert counts to inventory records
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

    def collect(self) -> List[Dict]:
        """
        Collect AWS resources.
        
        Uses Resource Explorer if available, otherwise falls back to direct API calls.
        
        Returns:
            List of inventory records.
        """
        logger.info("Starting AWS resource collection")

        all_inventory = []

        if self.use_organizations and self.organization_role:
            # Collect across organization
            accounts = self._get_org_accounts()
            logger.info("Collecting from %d organization accounts", len(accounts))

            for account in accounts:
                account_id = account['Id']
                account_name = account['Name']
                logger.info("Processing account: %s (%s)", account_name, account_id)

                if account_id == self.get_account_id():
                    # Current account, use default session
                    session = self._get_default_session()
                else:
                    # Assume role in member account
                    credentials = self._assume_role(account_id, self.organization_role)
                    if not credentials:
                        continue
                    session = self._get_session(credentials=credentials)

                # Collect from this account
                inventory = self._collect_from_account(session, account_id)
                all_inventory.extend(inventory)
        else:
            # Single account collection
            session = self._get_default_session()
            account_id = self.get_account_id()
            logger.info("Collecting from account: %s", account_id)
            all_inventory = self._collect_from_account(session, account_id)

        self._inventory = all_inventory
        logger.info("Collected %d inventory records from AWS", len(all_inventory))

        return all_inventory

    def _collect_from_account(self, session, account_id: str) -> List[Dict]:
        """Collect resources from a single AWS account using Resource Explorer."""
        logger.info("Querying Resource Explorer for account %s", account_id)
        return self._collect_via_resource_explorer(session, account_id)


def collect_aws(
    profile: str = None,
    region: str = "us-east-1",
    use_organizations: bool = False,
    organization_role: str = None,
    resource_mappings: Dict = None,
    output_path: str = None
) -> List[Dict]:
    """
    Convenience function to collect AWS resources.
    
    Args:
        profile: AWS profile name.
        region: AWS region for API calls.
        use_organizations: Whether to collect across org accounts.
        organization_role: IAM role to assume in member accounts.
        resource_mappings: Optional resource type mappings.
        output_path: Optional path to save inventory JSON.
        
    Returns:
        List of inventory records.
    """
    collector = AWSCollector(
        resource_mappings=resource_mappings,
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

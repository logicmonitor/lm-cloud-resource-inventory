"""AWS Resource Explorer collector for resource inventory."""

import logging
from typing import Dict, List, Optional

from .base import BaseCollector

logger = logging.getLogger(__name__)


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

            # Verify identity
            sts = session.client('sts')
            identity = sts.get_caller_identity()
            self._account_id = identity['Account']
            logger.info("AWS identity: %s", identity['Arn'])

            # Check if Resource Explorer is available
            rex = session.client('resource-explorer-2')

            try:
                # Try to list indexes to verify Resource Explorer is enabled
                indexes = rex.list_indexes()
                if not indexes.get('Indexes'):
                    logger.warning(
                        "AWS Resource Explorer is not enabled. "
                        "Please enable it for faster inventory collection. "
                        "Falling back to direct API calls."
                    )
                    return True  # Still allow collection via fallback

                logger.info("AWS Resource Explorer is enabled")
                return True

            except rex.exceptions.AccessDeniedException:
                logger.warning(
                    "No access to Resource Explorer. "
                    "Ensure the IAM policy includes resource-explorer-2:* permissions."
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

    def _is_resource_explorer_enabled(self, session) -> bool:
        """Check if Resource Explorer is enabled and has an aggregator index."""
        try:
            rex = session.client('resource-explorer-2')
            indexes = rex.list_indexes()

            # Check for an aggregator index
            for index in indexes.get('Indexes', []):
                if index.get('Type') == 'AGGREGATOR':
                    return True

            # If no aggregator, check for any local indexes
            return len(indexes.get('Indexes', [])) > 0

        except Exception as e:
            logger.debug("Resource Explorer check failed: %s", e)
            return False

    def _collect_via_resource_explorer(self, session, account_id: str) -> List[Dict]:
        """
        Collect resources using AWS Resource Explorer.
        
        This is the fast path - single API call for all resources.
        """
        rex = session.client('resource-explorer-2')
        inventory = []

        # Get all resource types and counts
        # Resource Explorer returns resources grouped by type
        paginator = rex.get_paginator('search')

        # Search for all resources
        resource_counts = {}

        try:
            for page in paginator.paginate(QueryString="*"):
                for resource in page.get('Resources', []):
                    resource_type = resource.get('ResourceType', '')
                    region = resource.get('Region', 'global')

                    key = (resource_type, region)
                    resource_counts[key] = resource_counts.get(key, 0) + 1

            # Convert counts to inventory records
            for (resource_type, region), count in resource_counts.items():
                record = self.create_inventory_record(
                    account_id=account_id,
                    region=region,
                    resource_type=resource_type,
                    count=count
                )
                inventory.append(record)

        except Exception as e:
            logger.error("Resource Explorer search failed: %s", e)

        return inventory

    def _collect_via_direct_apis(self, session, account_id: str) -> List[Dict]:
        """
        Collect resources using direct AWS service APIs.
        
        This is the slow fallback path when Resource Explorer is not available.
        Only collects the most common resource types.
        """
        inventory = []

        # Get list of enabled regions
        ec2 = session.client('ec2', region_name='us-east-1')
        regions = [r['RegionName'] for r in ec2.describe_regions()['Regions']]

        logger.warning(
            "Using direct API calls (slower). Scanning %d regions. This may take a while...",
            len(regions)
        )

        # Collect S3 (global service)
        try:
            s3 = session.client('s3')
            buckets = s3.list_buckets().get('Buckets', [])
            if buckets:
                record = self.create_inventory_record(
                    account_id=account_id,
                    region='global',
                    resource_type='AWS::S3::Bucket',
                    count=len(buckets)
                )
                inventory.append(record)
        except Exception as e:
            logger.debug("S3 collection failed: %s", e)

        # Collect regional services
        for region in regions:
            logger.debug("Scanning region: %s", region)

            # EC2 Instances
            try:
                ec2 = session.client('ec2', region_name=region)
                reservations = ec2.describe_instances().get('Reservations', [])
                count = sum(len(r.get('Instances', [])) for r in reservations)
                if count > 0:
                    record = self.create_inventory_record(
                        account_id=account_id,
                        region=region,
                        resource_type='AWS::EC2::Instance',
                        count=count
                    )
                    inventory.append(record)
            except Exception as e:
                logger.debug("EC2 collection failed in %s: %s", region, e)

            # Lambda Functions
            try:
                lam = session.client('lambda', region_name=region)
                functions = lam.list_functions().get('Functions', [])
                if functions:
                    record = self.create_inventory_record(
                        account_id=account_id,
                        region=region,
                        resource_type='AWS::Lambda::Function',
                        count=len(functions)
                    )
                    inventory.append(record)
            except Exception as e:
                logger.debug("Lambda collection failed in %s: %s", region, e)

            # RDS Instances
            try:
                rds = session.client('rds', region_name=region)
                instances = rds.describe_db_instances().get('DBInstances', [])
                if instances:
                    record = self.create_inventory_record(
                        account_id=account_id,
                        region=region,
                        resource_type='AWS::RDS::DBInstance',
                        count=len(instances)
                    )
                    inventory.append(record)
            except Exception as e:
                logger.debug("RDS collection failed in %s: %s", region, e)

        return inventory

    def _count_ec2_instances(self, response) -> int:
        """Count EC2 instances from describe_instances response."""
        count = 0
        for reservation in response.get('Reservations', []):
            count += len(reservation.get('Instances', []))
        return count

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
            all_inventory = self._collect_from_account(session, account_id)

        self._inventory = all_inventory
        logger.info("Collected %d inventory records from AWS", len(all_inventory))

        return all_inventory

    def _collect_from_account(self, session, account_id: str) -> List[Dict]:
        """Collect resources from a single AWS account."""
        if self._is_resource_explorer_enabled(session):
            logger.info("Using Resource Explorer for account %s", account_id)
            return self._collect_via_resource_explorer(session, account_id)
        else:
            logger.info("Using direct APIs for account %s (Resource Explorer not enabled)", account_id)
            return self._collect_via_direct_apis(session, account_id)


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

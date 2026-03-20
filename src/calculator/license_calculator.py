"""License calculator for processing inventory data."""

import json
import logging
import math
import re
from functools import lru_cache
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)

# Hybrid Resource Unit ratios (per LogicMonitor documentation)
# https://www.logicmonitor.com/support/usage-reporting-for-hybrid-resource-units
HYBRID_UNIT_RATIOS = {
    "IaaS": 1,      # 1 IaaS instance = 1 HRU
    "PaaS": 7,      # 7 PaaS resources = 1 HRU
}


class LicenseCalculator:
    """
    Calculate LogicMonitor license requirements from collected inventory.
    
    This class processes raw inventory data (JSON) and applies resource
    mappings to categorize resources into IaaS, PaaS, and Non-Compute.
    """

    CATEGORIES = ["IaaS", "PaaS", "Non-Compute", "No-Charge", "Unsupported"]

    def __init__(
        self,
        resource_mappings: Dict = None,
        license_rules: Dict = None
    ):
        """
        Initialize the license calculator.
        
        Args:
            resource_mappings: Dict mapping resource types to categories.
            license_rules: Dict with license calculation rules.
        """
        self.resource_mappings = resource_mappings or {}
        self.license_rules = license_rules or {}
        self._unsupported_types = set()

    @classmethod
    def from_config_files(
        cls,
        mappings_path: str = None,
        rules_path: str = None
    ) -> 'LicenseCalculator':
        """
        Create a LicenseCalculator from configuration files.
        
        Args:
            mappings_path: Path to resource_mappings.json
            rules_path: Path to license_rules.json
            
        Returns:
            Configured LicenseCalculator instance.
        """
        from ..utils.config_loader import load_resource_mappings, load_license_rules

        mappings = load_resource_mappings(mappings_path) if mappings_path else load_resource_mappings()
        rules = load_license_rules(rules_path) if rules_path else load_license_rules()

        return cls(resource_mappings=mappings, license_rules=rules)

    def get_category(self, provider: str, resource_type: str) -> str:
        """
        Get the license category for a resource type.
        
        Args:
            provider: Cloud provider (aws, azure, gcp, oci).
            resource_type: Provider-specific resource type.
            
        Returns:
            Category string (IaaS, PaaS, Non-Compute, No-Charge, or Unsupported).
        """
        # Check no-charge resources first
        no_charge = self.license_rules.get('no_charge_resources', {}).get(provider, [])
        for pattern in no_charge:
            if self._matches_pattern(resource_type, pattern):
                return "No-Charge"

        # Look up in mappings
        provider_mappings = self.resource_mappings.get(provider, {})

        canonical_type = self.normalize_resource_type(provider, resource_type)

        # Try exact match first
        resource_info = provider_mappings.get(canonical_type)
        if resource_info:
            return resource_info.get('category', 'Unsupported')

        # Try case-insensitive match
        resource_type_lower = canonical_type.lower()
        for mapped_type, info in provider_mappings.items():
            if mapped_type.lower() == resource_type_lower:
                return info.get('category', 'Unsupported')

        # Not found
        self._unsupported_types.add((provider, resource_type))
        return "Unsupported"

    def normalize_resource_type(self, provider: str, resource_type: str) -> str:
        """
        Normalize imported resource types to canonical mapping keys.

        This supports case-insensitive matching, friendly aliases, and
        provider-specific variants such as AWS CloudFormation-style names.
        """
        provider_mappings = self.resource_mappings.get(provider, {})
        if not provider_mappings or not resource_type:
            return resource_type

        if resource_type in provider_mappings:
            return resource_type

        alias_index = self._build_alias_index(provider)
        normalized_key = self._normalize_alias(resource_type)
        return alias_index.get(normalized_key, resource_type)

    @staticmethod
    def _normalize_alias(value: str) -> str:
        """Normalize a resource label for case-insensitive alias matching."""
        normalized = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', value or '')
        normalized = normalized.replace('::', ' ')
        normalized = normalized.replace('/', ' ')
        normalized = normalized.replace(':', ' ')
        normalized = normalized.replace('-', ' ')
        normalized = normalized.replace('_', ' ')
        normalized = normalized.replace('.', ' ')
        normalized = re.sub(r'\s+', ' ', normalized.lower()).strip()
        return normalized

    @staticmethod
    def _humanize_provider_leaf(provider: str, resource_type: str) -> str:
        """Convert a provider resource key into a readable alias candidate."""
        if provider == 'aws' and ':' in resource_type:
            service, raw_type = resource_type.split(':', 1)
            value = f"{service} {raw_type}"
        elif provider == 'azure' and '/' in resource_type:
            segments = resource_type.split('/')
            value = ' '.join(segment for segment in segments[1:] if segment)
        else:
            value = resource_type.split('/')[-1].split(':')[-1]

        value = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', value)
        value = re.sub(r'(?<=[a-z])(?=(instances|machines|clusters|groups|accounts|servers|vaults|services|jobs|rules|plans|apps|sets|pools|zones|profiles|balances|interfaces|addresses|gateways|databases|workspaces|registries))', ' ', value, flags=re.IGNORECASE)
        return re.sub(r'\s+', ' ', value).strip()

    @classmethod
    def _generate_aliases(cls, provider: str, resource_type: str, resource_info: Dict) -> Set[str]:
        """Generate alias candidates for a canonical resource mapping."""
        aliases = {resource_type}
        aliases.add(cls._humanize_provider_leaf(provider, resource_type))

        unit = resource_info.get('unit')
        if unit:
            aliases.add(unit)

        if provider == 'aws' and ':' in resource_type:
            service, raw_type = resource_type.split(':', 1)
            aliases.add(f"AWS::{service.upper()}::{raw_type.replace('-', '').replace('/', '').upper()}")
            aliases.add(f"AWS::{service}::{raw_type}")
            aliases.add(f"{service} {raw_type}")

        for alias in resource_info.get('aliases', []):
            aliases.add(alias)

        return {alias for alias in aliases if alias}

    @lru_cache(maxsize=None)
    def _build_alias_index(self, provider: str) -> Dict[str, str]:
        """Build a normalized alias index for one provider."""
        alias_index = {}
        provider_mappings = self.resource_mappings.get(provider, {})

        for resource_type, resource_info in provider_mappings.items():
            for alias in self._generate_aliases(provider, resource_type, resource_info):
                alias_index[self._normalize_alias(alias)] = resource_type

        return alias_index

    def _matches_pattern(self, resource_type: str, pattern: str) -> bool:
        """
        Check if resource type matches a pattern.
        
        Supports wildcards (*) for pattern matching.
        
        Args:
            resource_type: Resource type to check.
            pattern: Pattern with optional wildcards.
            
        Returns:
            True if matches, False otherwise.
        """
        if '*' not in pattern:
            return resource_type == pattern

        # Simple wildcard matching
        if pattern.endswith('*'):
            prefix = pattern[:-1]
            return resource_type.startswith(prefix)

        if pattern.startswith('*'):
            suffix = pattern[1:]
            return resource_type.endswith(suffix)

        # Middle wildcard
        parts = pattern.split('*')
        return resource_type.startswith(parts[0]) and resource_type.endswith(parts[-1])

    def get_unsupported_types(self) -> Set[Tuple[str, str]]:
        """
        Get the set of unsupported resource types encountered.
        
        Returns:
            Set of (provider, resource_type) tuples.
        """
        return self._unsupported_types

    def calculate_hybrid_units(self, iaas_count: int, paas_count: int) -> int:
        """
        Calculate Hybrid Resource Units from IaaS and PaaS counts.
        
        Per LogicMonitor documentation:
        - IaaS: 1:1 ratio (1 IaaS = 1 HRU)
        - PaaS: 7:1 ratio (7 PaaS = 1 HRU, rounded UP)
        
        Args:
            iaas_count: Total IaaS resource count.
            paas_count: Total PaaS resource count.
            
        Returns:
            Total Hybrid Resource Units.
        """
        iaas_hru = iaas_count  # 1:1 ratio
        paas_hru = math.ceil(paas_count / HYBRID_UNIT_RATIOS["PaaS"]) if paas_count > 0 else 0
        return iaas_hru + paas_hru

    def calculate(self, inventory: List[Dict]) -> Dict:
        """
        Calculate license requirements from inventory.
        
        Args:
            inventory: List of inventory records from collectors.
            
        Returns:
            Dict with summary and detailed results.
        """
        logger.info("Calculating license requirements from %d records", len(inventory))

        # Group by category
        summary = defaultdict(lambda: defaultdict(int))
        detailed = []

        for record in inventory:
            provider = record.get('provider', 'unknown')
            account_id = record.get('account_id', '')
            region = record.get('region', '')
            original_resource_type = record.get('resource_type', '')
            resource_type = self.normalize_resource_type(provider, original_resource_type)
            count = record.get('count', 0)

            category = self.get_category(provider, resource_type)

            # Add to summary
            summary[provider][category] += count

            # Add to detailed results
            detailed.append({
                'provider': provider,
                'account_id': account_id,
                'region': region,
                'resource_type': resource_type,
                'category': category,
                'count': count
            })

        # Create totals
        totals = defaultdict(int)
        for provider_summary in summary.values():
            for category, count in provider_summary.items():
                totals[category] += count

        # Calculate Hybrid Resource Units
        hybrid_units = self.calculate_hybrid_units(
            totals.get('IaaS', 0),
            totals.get('PaaS', 0)
        )

        result = {
            'summary': {
                'by_provider': dict(summary),
                'totals': dict(totals),
                'hybrid_units': hybrid_units
            },
            'detailed': detailed,
            'unsupported_types': list(self._unsupported_types)
        }

        return result

    def calculate_from_file(self, input_path: str) -> Dict:
        """
        Calculate license requirements from an inventory file.
        
        Args:
            input_path: Path to inventory JSON file.
            
        Returns:
            Dict with summary and detailed results.
        """
        with open(input_path, 'r', encoding='utf-8') as f:
            inventory = json.load(f)

        return self.calculate(inventory)

    def save_summary_csv(self, results: Dict, output_path: str) -> None:
        """
        Save detailed summary results to a CSV file.
        
        Includes full breakdown by provider, account, category, resource type, and region.
        This allows users to analyze and filter results as needed.
        
        Args:
            results: Results from calculate().
            output_path: Path to output CSV file.
        """
        import csv

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Provider', 'Account', 'Category', 'ResourceType', 'Region', 'Count'])

            # Sort by provider, category, resource type, region for clean output
            sorted_records = sorted(
                [r for r in results['detailed'] if r['category'] not in ('Unsupported', 'No-Charge')],
                key=lambda x: (x['provider'], x['category'], x['resource_type'], x['region'])
            )

            for record in sorted_records:
                writer.writerow([
                    record['provider'],
                    record['account_id'],
                    record['category'],
                    record['resource_type'],
                    record['region'],
                    record['count']
                ])

            # Add blank row before totals
            writer.writerow([])

            # Add totals rows
            for category in ['IaaS', 'PaaS', 'Non-Compute']:
                count = results['summary']['totals'].get(category, 0)
                if count > 0:
                    writer.writerow(['TOTAL', '', category, '', '', count])

            # Add Hybrid Resource Units row
            hybrid_units = results['summary'].get('hybrid_units', 0)
            writer.writerow(['TOTAL', '', 'HYBRID UNITS', '', '', hybrid_units])

        logger.info("Saved summary to %s", output_path)

    def save_detailed_csv(self, results: Dict, output_path: str) -> None:
        """
        Save detailed results to a CSV file.
        
        Args:
            results: Results from calculate().
            output_path: Path to output CSV file.
        """
        import csv

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Provider', 'Account', 'Region', 'ResourceType', 'Category', 'Count'])

            for record in results['detailed']:
                if record['category'] != 'Unsupported':
                    writer.writerow([
                        record['provider'],
                        record['account_id'],
                        record['region'],
                        record['resource_type'],
                        record['category'],
                        record['count']
                    ])

        logger.info("Saved detailed results to %s", output_path)

    def print_summary(self, results: Dict) -> None:
        """
        Print a formatted summary of results with resource type breakdown.
        
        Args:
            results: Results from calculate().
        """
        print("\n" + "=" * 70)
        print("LICENSE REQUIREMENT SUMMARY")
        print("=" * 70)

        # Build resource type breakdown by provider -> category -> resource_type
        # Aggregate counts across regions for cleaner CLI output
        breakdown = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
        for record in results['detailed']:
            if record['category'] not in ('Unsupported', 'No-Charge'):
                provider = record['provider']
                category = record['category']
                resource_type = record['resource_type']
                breakdown[provider][category][resource_type] += record['count']

        # Per-provider summary with resource type breakdown
        for provider in sorted(breakdown.keys()):
            print(f"\n{provider.upper()}")
            print("-" * 40)

            provider_categories = results['summary']['by_provider'].get(provider, {})
            for category in ['IaaS', 'PaaS', 'Non-Compute']:
                cat_total = provider_categories.get(category, 0)
                if cat_total > 0:
                    print(f"  {category:20} {cat_total:>10}")
                    # Show resource types under this category
                    resource_types = breakdown[provider][category]
                    for res_type, count in sorted(resource_types.items(),
                                                   key=lambda x: -x[1]):
                        print(f"    {res_type:36} {count:>6}")

        # Totals (category totals only, no breakdown)
        print("\n" + "=" * 70)
        print("TOTALS")
        print("-" * 40)
        for category in ['IaaS', 'PaaS', 'Non-Compute']:
            count = results['summary']['totals'].get(category, 0)
            if count > 0:
                print(f"  {category:20} {count:>10}")

        # Hybrid Resource Units
        hybrid_units = results['summary'].get('hybrid_units', 0)
        iaas_count = results['summary']['totals'].get('IaaS', 0)
        paas_count = results['summary']['totals'].get('PaaS', 0)
        paas_hru = math.ceil(paas_count / HYBRID_UNIT_RATIOS["PaaS"]) if paas_count > 0 else 0
        print("-" * 40)
        print(f"  {'HYBRID RESOURCE UNITS':20} {hybrid_units:>10}")
        print(f"    (IaaS: {iaas_count} + PaaS: {paas_hru})")

        # Unmapped types notice
        unsupported = self.get_unsupported_types()
        if unsupported:
            print("\n" + "=" * 70)
            print(f"NOTE: {len(unsupported)} resource types not mapped to license categories")
            print("These are typically infrastructure/config resources (IAM, VPC, etc.)")
            print("that don't count toward licensing. Use --show-unmapped to list them.")

        print("=" * 70 + "\n")


def calculate_licenses(
    input_path: str,
    output_path: str = None,
    detailed_output_path: str = None,
    mappings_path: str = None,
    rules_path: str = None,
    show_unsupported: bool = False
) -> Dict:
    """
    Convenience function to calculate licenses from inventory file.
    
    Args:
        input_path: Path to inventory JSON file.
        output_path: Optional path for summary CSV.
        detailed_output_path: Optional path for detailed CSV.
        mappings_path: Optional path to resource mappings.
        rules_path: Optional path to license rules.
        show_unsupported: Whether to print unsupported resource types.
        
    Returns:
        Results dictionary.
    """
    calculator = LicenseCalculator.from_config_files(mappings_path, rules_path)
    results = calculator.calculate_from_file(input_path)

    if output_path:
        calculator.save_summary_csv(results, output_path)

    if detailed_output_path:
        calculator.save_detailed_csv(results, detailed_output_path)

    calculator.print_summary(results)

    unsupported = calculator.get_unsupported_types()
    if show_unsupported and unsupported:
        print("\nUnsupported Resource Types:")
        print("-" * 40)
        for provider, resource_type in sorted(unsupported):
            print(f"  [{provider}] {resource_type}")

    return results

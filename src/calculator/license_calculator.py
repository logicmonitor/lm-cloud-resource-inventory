"""License calculator for processing inventory data."""

import json
import logging
from typing import Dict, List, Set, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


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

        # Try exact match first
        resource_info = provider_mappings.get(resource_type)
        if resource_info:
            return resource_info.get('category', 'Unsupported')

        # Try case-insensitive match
        resource_type_lower = resource_type.lower()
        for mapped_type, info in provider_mappings.items():
            if mapped_type.lower() == resource_type_lower:
                return info.get('category', 'Unsupported')

        # Not found
        self._unsupported_types.add((provider, resource_type))
        return "Unsupported"

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
            resource_type = record.get('resource_type', '')
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

        result = {
            'summary': {
                'by_provider': dict(summary),
                'totals': dict(totals)
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
        Save summary results to a CSV file.
        
        Args:
            results: Results from calculate().
            output_path: Path to output CSV file.
        """
        import csv

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Provider', 'Category', 'Count'])

            for provider, categories in results['summary']['by_provider'].items():
                for category, count in sorted(categories.items()):
                    if category != 'Unsupported':  # Exclude unsupported from summary
                        writer.writerow([provider, category, count])

            # Add totals row
            writer.writerow([])
            writer.writerow(['TOTAL', '', ''])
            for category, count in sorted(results['summary']['totals'].items()):
                if category != 'Unsupported':
                    writer.writerow(['', category, count])

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
        Print a formatted summary of results.
        
        Args:
            results: Results from calculate().
        """
        print("\n" + "=" * 70)
        print("LICENSE REQUIREMENT SUMMARY")
        print("=" * 70)

        # Per-provider summary
        for provider, categories in sorted(results['summary']['by_provider'].items()):
            print(f"\n{provider.upper()}")
            print("-" * 40)
            for category, count in sorted(categories.items()):
                if category != 'Unsupported':
                    print(f"  {category:20} {count:>10}")

        # Totals
        print("\n" + "=" * 70)
        print("TOTALS")
        print("-" * 40)
        for category, count in sorted(results['summary']['totals'].items()):
            if category != 'Unsupported':
                print(f"  {category:20} {count:>10}")

        # Unsupported types warning
        unsupported = self.get_unsupported_types()
        if unsupported:
            print("\n" + "=" * 70)
            print(f"WARNING: {len(unsupported)} unsupported resource types found")
            print("These resources are not counted toward license requirements.")
            print("Run with --show-unsupported to see the list.")

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

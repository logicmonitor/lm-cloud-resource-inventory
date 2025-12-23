"""
LM Cloud Resource Inventory - Command Line Interface

A unified CLI for collecting cloud resource inventory across
AWS, Azure, GCP, and OCI for LogicMonitor licensing.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Optional

from . import __version__

try:
    import click
    from rich.console import Console
    from rich.logging import RichHandler
except ImportError:
    print("Required packages not installed. Run: pip install click rich")
    sys.exit(1)

console = Console()


def setup_logging(verbose: bool = False):
    """Configure logging with rich output."""
    # Configure our application logger only (not root logger)
    app_logger = logging.getLogger('src')
    app_logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    # Add rich handler if not already added
    if not app_logger.handlers:
        handler = RichHandler(
            console=console,
            rich_tracebacks=True,
            omit_repeated_times=False  # Show timestamp on every log line
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        app_logger.addHandler(handler)

    # Suppress noisy third-party SDK loggers
    noisy_loggers = [
        'azure', 'azure.core', 'azure.identity', 'azure.mgmt',
        'urllib3', 'msrest', 'msal',
        'boto3', 'botocore', 's3transfer',
        'google', 'google.auth', 'google.cloud',
        'oci',
        'httpx', 'httpcore'
    ]
    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


@click.group()
@click.version_option(version=__version__)
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
def cli(verbose: bool):
    """
    LM Cloud Resource Inventory
    
    Collect cloud resource counts for LogicMonitor licensing.
    
    Supported providers: aws, azure, gcp, oci
    """
    setup_logging(verbose)


@cli.command()
@click.option('--provider', '-p', required=True,
              type=click.Choice(['aws', 'azure', 'gcp', 'oci']),
              help='Cloud provider to collect from')
@click.option('--output', '-o', default='inventory.json',
              help='Output file path (default: inventory.json)')
@click.option('--profile', help='AWS profile name')
@click.option('--region', default='us-east-1', help='AWS region (default: us-east-1)')
@click.option('--subscription', '-s', multiple=True,
              help='Azure subscription ID(s)')
@click.option('--project', help='GCP project ID')
@click.option('--organization', help='GCP organization ID or AWS organization role')
@click.option('--compartment', help='OCI compartment OCID')
def collect(
    provider: str,
    output: str,
    profile: Optional[str],
    region: str,
    subscription: tuple,
    project: Optional[str],
    organization: Optional[str],
    compartment: Optional[str]
):
    """
    Collect resource inventory from a cloud provider.
    
    Examples:
    
      lm-cloud-inventory collect -p aws -o aws_inventory.json
      
      lm-cloud-inventory collect -p azure -s sub-id-1 -s sub-id-2
      
      lm-cloud-inventory collect -p gcp --project my-project
      
      lm-cloud-inventory collect -p oci --compartment ocid.compartment...
    """
    console.print(f"\n[bold blue]Collecting {provider.upper()} resources...[/bold blue]\n")

    try:
        if provider == 'aws':
            from .collectors import collect_aws

            use_org = bool(organization)
            collect_aws(
                profile=profile,
                region=region,
                use_organizations=use_org,
                organization_role=organization if use_org else None,
                output_path=output
            )

        elif provider == 'azure':
            from .collectors import collect_azure

            subscription_ids = list(subscription) if subscription else None
            collect_azure(
                subscriptions=subscription_ids,
                output_path=output
            )

        elif provider == 'gcp':
            from .collectors import collect_gcp

            collect_gcp(
                project_id=project,
                organization_id=organization,
                output_path=output
            )

        elif provider == 'oci':
            from .collectors import collect_oci

            collect_oci(
                compartment_id=compartment,
                output_path=output
            )

        console.print(f"\n[green]✓ Inventory saved to {output}[/green]")
        console.print(f"[dim]Run 'lm-cloud-inventory calculate -i {output}' to generate license summary[/dim]\n")

    except ImportError as e:
        console.print(f"[red]Missing dependency: {e}[/red]")
        console.print("[yellow]Install required packages with: pip install -r requirements.txt[/yellow]")
        sys.exit(1)

    except PermissionError as e:
        console.print(f"[red]Permission error: {e}[/red]")
        console.print("[yellow]See docs/PERMISSIONS.md for required permissions.[/yellow]")
        sys.exit(1)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logging.exception("Collection failed")
        sys.exit(1)


@cli.command()
@click.option('--input', '-i', 'input_path', required=True,
              help='Input inventory JSON file')
@click.option('--output', '-o', default='license_summary.csv',
              help='Output summary CSV file')
@click.option('--detailed', '-d', is_flag=True,
              help='Generate detailed output with resource breakdown')
@click.option('--show-unsupported', is_flag=True,
              help='Show unsupported resource types')
def calculate(
    input_path: str,
    output: str,
    detailed: bool,
    show_unsupported: bool
):
    """
    Calculate license requirements from inventory.
    
    Examples:
    
      lm-cloud-inventory calculate -i inventory.json -o summary.csv
      
      lm-cloud-inventory calculate -i inventory.json -d --show-unsupported
    """
    console.print("\n[bold blue]Calculating license requirements...[/bold blue]\n")

    try:
        from .calculator import LicenseCalculator

        # Load inventory
        with open(input_path, 'r', encoding='utf-8') as f:
            inventory = json.load(f)

        # Create calculator with default config
        calculator = LicenseCalculator.from_config_files()

        # Calculate
        results = calculator.calculate(inventory)

        # Save summary
        calculator.save_summary_csv(results, output)

        # Save detailed if requested
        if detailed:
            detailed_path = output.replace('.csv', '_detailed.csv')
            calculator.save_detailed_csv(results, detailed_path)
            console.print(f"[green]✓ Detailed results saved to {detailed_path}[/green]")

        # Print summary
        calculator.print_summary(results)

        # Show unsupported types if requested
        unsupported = calculator.get_unsupported_types()
        if show_unsupported and unsupported:
            console.print("\n[yellow]Unsupported Resource Types:[/yellow]")
            for prov, resource_type in sorted(unsupported):
                console.print(f"  [{prov}] {resource_type}")

        console.print(f"\n[green]✓ Summary saved to {output}[/green]\n")

    except FileNotFoundError:
        console.print(f"[red]Error: Input file not found: {input_path}[/red]")
        sys.exit(1)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logging.exception("Calculation failed")
        sys.exit(1)


@cli.command()
@click.option('--provider', '-p', required=True,
              type=click.Choice(['aws', 'azure', 'gcp', 'oci']),
              help='Cloud provider')
@click.option('--output', '-o', default='license_summary.csv',
              help='Output summary CSV file')
@click.option('--detailed', '-d', is_flag=True,
              help='Generate detailed output')
@click.option('--profile', help='AWS profile name')
@click.option('--subscription', '-s', multiple=True,
              help='Azure subscription ID(s)')
@click.option('--project', help='GCP project ID')
@click.option('--compartment', help='OCI compartment OCID')
def run(
    provider: str,
    output: str,
    detailed: bool,
    profile: Optional[str],
    subscription: tuple,
    project: Optional[str],
    compartment: Optional[str]
):
    """
    Collect inventory and calculate licenses in one step.
    
    Examples:
    
      lm-cloud-inventory run -p aws -o aws_summary.csv
      
      lm-cloud-inventory run -p azure -d
    """
    import tempfile

    console.print(f"\n[bold blue]Running full inventory and calculation for {provider.upper()}...[/bold blue]\n")

    inventory = None

    try:
        # Collect to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_inventory = f.name

        # Run collection
        if provider == 'aws':
            from .collectors import collect_aws
            inventory = collect_aws(profile=profile, output_path=temp_inventory)

        elif provider == 'azure':
            from .collectors import collect_azure
            subscription_ids = list(subscription) if subscription else None
            inventory = collect_azure(subscriptions=subscription_ids, output_path=temp_inventory)

        elif provider == 'gcp':
            from .collectors import collect_gcp
            inventory = collect_gcp(project_id=project, output_path=temp_inventory)

        elif provider == 'oci':
            from .collectors import collect_oci
            inventory = collect_oci(compartment_id=compartment, output_path=temp_inventory)

        # Calculate licenses
        from .calculator import LicenseCalculator

        calculator = LicenseCalculator.from_config_files()
        results = calculator.calculate(inventory)

        # Save outputs
        calculator.save_summary_csv(results, output)

        if detailed:
            detailed_path = output.replace('.csv', '_detailed.csv')
            calculator.save_detailed_csv(results, detailed_path)
            console.print(f"[green]✓ Detailed results saved to {detailed_path}[/green]")

        # Also save raw inventory
        inventory_path = output.replace('.csv', '_inventory.json')
        with open(inventory_path, 'w', encoding='utf-8') as f:
            json.dump(inventory, f, indent=2, default=str)
        console.print(f"[green]✓ Raw inventory saved to {inventory_path}[/green]")

        # Print summary
        calculator.print_summary(results)

        console.print(f"\n[green]✓ Summary saved to {output}[/green]\n")

        # Cleanup temp file
        Path(temp_inventory).unlink(missing_ok=True)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logging.exception("Run failed")
        sys.exit(1)


@cli.command()
@click.option('--provider', '-p',
              type=click.Choice(['aws', 'azure', 'gcp', 'oci']),
              help='Show permissions for specific provider')
def permissions(provider: Optional[str]):
    """
    Show required permissions for each cloud provider.
    """
    if provider:
        providers = [provider]
    else:
        providers = ['aws', 'azure', 'gcp', 'oci']

    for p in providers:
        console.print(f"\n[bold blue]{p.upper()} Permissions[/bold blue]")
        console.print("-" * 40)

        if p == 'aws':
            console.print("""
Required IAM permissions:
  - resource-explorer-2:Search
  - resource-explorer-2:ListViews
  - resource-explorer-2:GetView
  - sts:GetCallerIdentity

For AWS Organizations:
  - organizations:ListAccounts
  - sts:AssumeRole (for member accounts)

Recommended: Use AWS Resource Explorer with an aggregator index.
See docs/PERMISSIONS.md for full policy examples.
            """)

        elif p == 'azure':
            console.print("""
Required role: Reader

Assign at subscription or management group level:
  az role assignment create \\
    --assignee <user-or-sp> \\
    --role "Reader" \\
    --scope "/subscriptions/<sub-id>"

See docs/PERMISSIONS.md for full instructions.
            """)

        elif p == 'gcp':
            console.print("""
Required role: roles/cloudasset.viewer

Grant access:
  gcloud projects add-iam-policy-binding <project> \\
    --member="user:you@example.com" \\
    --role="roles/cloudasset.viewer"

See docs/PERMISSIONS.md for full instructions.
            """)

        elif p == 'oci':
            console.print("""
Required policy:
  Allow group <group> to inspect all-resources in tenancy

Create policy in OCI Console or via CLI:
  oci iam policy create \\
    --name "LMInventoryReadOnly" \\
    --statements '["Allow group LMInventory to inspect all-resources in tenancy"]'

See docs/PERMISSIONS.md for full instructions.
            """)


def main():
    """Entry point for the CLI."""
    cli()  # pylint: disable=no-value-for-parameter


if __name__ == '__main__':
    main()

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

# Maps provider -> set of relevant option names
PROVIDER_OPTIONS = {
    'aws': {'profile', 'region', 'organization'},
    'azure': {'subscription'},
    'gcp': {'project', 'organization'},
    'oci': {'compartment'},
}


def setup_logging(verbose: bool = False):
    """Configure logging with rich output."""
    app_logger = logging.getLogger('src')
    app_logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    if not app_logger.handlers:
        handler = RichHandler(
            console=console,
            rich_tracebacks=True,
            omit_repeated_times=False
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        app_logger.addHandler(handler)

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


def _warn_irrelevant_options(provider: str, **options):
    """Warn if provider-irrelevant options are supplied."""
    relevant = PROVIDER_OPTIONS.get(provider, set())
    for name, value in options.items():
        if value and name not in relevant:
            has_value = value if not isinstance(value, tuple) else bool(value)
            if has_value:
                console.print(
                    f"[yellow]Warning: --{name} is not used with provider '{provider}' and will be ignored[/yellow]"
                )


def _derive_path(base_path: str, suffix: str, new_ext: str = None) -> str:
    """
    Derive a related output path from a base path.
    
    Inserts suffix before the extension. Optionally changes the extension.
    E.g. _derive_path("out.csv", "_detailed") -> "out_detailed.csv"
         _derive_path("out.csv", "_inventory", ".json") -> "out_inventory.json"
    """
    p = Path(base_path)
    stem = p.stem
    ext = new_ext if new_ext else p.suffix
    return str(p.with_name(f"{stem}{suffix}{ext}"))


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
    _warn_irrelevant_options(
        provider,
        profile=profile, region=region if region != 'us-east-1' else None,
        subscription=subscription, project=project,
        organization=organization, compartment=compartment
    )

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
        if logging.getLogger('src').level == logging.DEBUG:
            logging.exception("Collection failed")
        sys.exit(1)


@cli.command()
@click.option('--input', '-i', 'input_path', required=True,
              help='Input inventory JSON file')
@click.option('--output', '-o', default='license_summary.csv',
              help='Output summary CSV file')
@click.option('--detailed', '-d', is_flag=True,
              help='Generate detailed output with resource breakdown')
@click.option('--show-unmapped', is_flag=True,
              help='List resource types not mapped to license categories')
def calculate(
    input_path: str,
    output: str,
    detailed: bool,
    show_unmapped: bool
):
    """
    Calculate license requirements from inventory.
    
    Examples:
    
      lm-cloud-inventory calculate -i inventory.json -o summary.csv
      
      lm-cloud-inventory calculate -i inventory.json -d --show-unmapped
    """
    console.print("\n[bold blue]Calculating license requirements...[/bold blue]\n")

    try:
        from .calculator import LicenseCalculator

        with open(input_path, 'r', encoding='utf-8') as f:
            inventory = json.load(f)

        if not isinstance(inventory, list):
            console.print("[red]Error: Inventory file must contain a JSON array of records.[/red]")
            sys.exit(1)

        calculator = LicenseCalculator.from_config_files()

        results = calculator.calculate(inventory)

        calculator.save_summary_csv(results, output)

        if detailed:
            detailed_path = _derive_path(output, '_detailed')
            calculator.save_detailed_csv(results, detailed_path)
            console.print(f"[green]✓ Detailed results saved to {detailed_path}[/green]")

        calculator.print_summary(results)

        unmapped = calculator.get_unsupported_types()
        if show_unmapped and unmapped:
            console.print("\n[dim]Unmapped Resource Types (not counted toward licensing):[/dim]")
            for _, resource_type in sorted(unmapped):
                console.print(f"   {resource_type}")

        console.print(f"\n[green]✓ Summary saved to {output}[/green]\n")

    except FileNotFoundError:
        console.print(f"[red]Error: Input file not found: {input_path}[/red]")
        sys.exit(1)

    except json.JSONDecodeError as e:
        console.print(f"[red]Error: Invalid JSON in {input_path}: {e}[/red]")
        sys.exit(1)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        if logging.getLogger('src').level == logging.DEBUG:
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
@click.option('--show-unmapped', is_flag=True,
              help='List resource types not mapped to license categories')
@click.option('--profile', help='AWS profile name')
@click.option('--region', default='us-east-1', help='AWS region (default: us-east-1)')
@click.option('--subscription', '-s', multiple=True,
              help='Azure subscription ID(s)')
@click.option('--project', help='GCP project ID')
@click.option('--organization', help='GCP organization ID or AWS organization role')
@click.option('--compartment', help='OCI compartment OCID')
def run(
    provider: str,
    output: str,
    detailed: bool,
    show_unmapped: bool,
    profile: Optional[str],
    region: str,
    subscription: tuple,
    project: Optional[str],
    organization: Optional[str],
    compartment: Optional[str]
):
    """
    Collect inventory and calculate licenses in one step.
    
    Examples:
    
      lm-cloud-inventory run -p aws -o aws_summary.csv
      
      lm-cloud-inventory run -p azure -d --show-unmapped
      
      lm-cloud-inventory run -p aws --organization MyOrgRole --region us-west-2
    """
    import tempfile

    _warn_irrelevant_options(
        provider,
        profile=profile, region=region if region != 'us-east-1' else None,
        subscription=subscription, project=project,
        organization=organization, compartment=compartment
    )

    console.print(f"\n[bold blue]Running full inventory and calculation for {provider.upper()}...[/bold blue]\n")

    inventory = None
    temp_inventory = None

    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_inventory = f.name

        if provider == 'aws':
            from .collectors import collect_aws
            use_org = bool(organization)
            inventory = collect_aws(
                profile=profile,
                region=region,
                use_organizations=use_org,
                organization_role=organization if use_org else None,
                output_path=temp_inventory
            )

        elif provider == 'azure':
            from .collectors import collect_azure
            subscription_ids = list(subscription) if subscription else None
            inventory = collect_azure(subscriptions=subscription_ids, output_path=temp_inventory)

        elif provider == 'gcp':
            from .collectors import collect_gcp
            inventory = collect_gcp(project_id=project, organization_id=organization, output_path=temp_inventory)

        elif provider == 'oci':
            from .collectors import collect_oci
            inventory = collect_oci(compartment_id=compartment, output_path=temp_inventory)

        from .calculator import LicenseCalculator

        calculator = LicenseCalculator.from_config_files()
        results = calculator.calculate(inventory)

        calculator.save_summary_csv(results, output)

        if detailed:
            detailed_path = _derive_path(output, '_detailed')
            calculator.save_detailed_csv(results, detailed_path)
            console.print(f"[green]✓ Detailed results saved to {detailed_path}[/green]")

        inventory_path = _derive_path(output, '_inventory', '.json')
        with open(inventory_path, 'w', encoding='utf-8') as f:
            json.dump(inventory, f, indent=2, default=str)
        console.print(f"[green]✓ Raw inventory saved to {inventory_path}[/green]")

        calculator.print_summary(results)

        unmapped = calculator.get_unsupported_types()
        if show_unmapped and unmapped:
            console.print("\n[dim]Unmapped Resource Types (not counted toward licensing):[/dim]")
            for _, resource_type in sorted(unmapped):
                console.print(f"   {resource_type}")

        console.print(f"\n[green]✓ Summary saved to {output}[/green]\n")

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
        if logging.getLogger('src').level == logging.DEBUG:
            logging.exception("Run failed")
        sys.exit(1)

    finally:
        if temp_inventory:
            Path(temp_inventory).unlink(missing_ok=True)


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

"""
LM Cloud Resource Inventory - Command Line Interface

A unified CLI for collecting cloud resource inventory across
AWS, Azure, GCP, and OCI for LogicMonitor licensing.
"""

import json
import logging
import re
import shutil
import sys
from pathlib import Path
from typing import Optional

from . import __version__

try:
    import click
    from rich.console import Console
    from rich.logging import RichHandler
    from rich.markup import escape
except ImportError:
    print(f'Required packages not installed. Run: "{sys.executable}" -m pip install click rich')
    sys.exit(1)

console = Console()

# Maps provider -> set of relevant option names
PROVIDER_OPTIONS = {
    'aws': {'profile', 'region', 'organization'},
    'azure': {'subscription'},
    'gcp': {'project', 'organization'},
    'oci': {'compartment'},
}

PROVIDER_DEPENDENCIES = {
    'aws': [('boto3', 'boto3')],
    'azure': [
        ('azure-identity', 'azure.identity'),
        ('azure-mgmt-resourcegraph', 'azure.mgmt.resourcegraph'),
        ('azure-mgmt-resource-subscriptions', 'azure.mgmt.resource.subscriptions'),
    ],
    'gcp': [('google-cloud-asset', 'google.cloud.asset_v1')],
    'oci': [('oci', 'oci')],
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
        if name not in relevant and (value if not isinstance(value, tuple) else bool(value)):
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


def _get_install_hint(provider: str) -> str:
    """Get the install command hint for a provider."""
    package = f"lm-cloud-inventory[{provider}]"
    return f'"{sys.executable}" -m pip install "{package}"'


def _get_all_install_hint() -> str:
    """Get an install command that targets the interpreter running the CLI."""
    return f'"{sys.executable}" -m pip install "lm-cloud-inventory[all]"'


_UUID_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE
)
_GCP_PROJECT_RE = re.compile(r'^[a-z][a-z0-9-]{4,28}[a-z0-9]$')
_OCID_PREFIX = 'ocid1.'


def _validate_ids(provider: str, **kwargs):
    """Warn about IDs that don't match the expected format for a provider."""
    if provider == 'azure':
        subs = kwargs.get('subscription')
        if subs:
            for sub in subs:
                if not _UUID_RE.match(sub):
                    console.print(
                        f"[yellow]Warning: '{sub}' does not look like a valid "
                        f"Azure subscription GUID[/yellow]"
                    )
    elif provider == 'gcp':
        project = kwargs.get('project')
        if project and not _GCP_PROJECT_RE.match(project):
            console.print(
                f"[yellow]Warning: '{project}' does not look like a valid "
                f"GCP project ID (expected lowercase alphanumeric + hyphens, 6-30 chars)[/yellow]"
            )
    elif provider == 'oci':
        compartment = kwargs.get('compartment')
        if compartment and not compartment.startswith(_OCID_PREFIX):
            console.print(
                f"[yellow]Warning: '{compartment}' does not look like a valid "
                f"OCI OCID (expected to start with '{_OCID_PREFIX}')[/yellow]"
            )


def _dispatch_collect(provider: str, output_path: str, **kwargs):
    """Dispatch to the correct collector based on provider name."""
    _validate_ids(provider, **kwargs)

    if provider == 'aws':
        from .collectors import collect_aws  # pylint: disable=no-name-in-module
        use_org = bool(kwargs.get('organization'))
        return collect_aws(
            profile=kwargs.get('profile'),
            region=kwargs.get('region', 'us-east-1'),
            use_organizations=use_org,
            organization_role=kwargs['organization'] if use_org else None,
            output_path=output_path,
        )
    elif provider == 'azure':
        from .collectors import collect_azure  # pylint: disable=no-name-in-module
        subs = list(kwargs['subscription']) if kwargs.get('subscription') else None
        return collect_azure(subscriptions=subs, output_path=output_path)
    elif provider == 'gcp':
        from .collectors import collect_gcp  # pylint: disable=no-name-in-module
        return collect_gcp(
            project_id=kwargs.get('project'),
            organization_id=kwargs.get('organization'),
            output_path=output_path,
        )
    elif provider == 'oci':
        from .collectors import collect_oci  # pylint: disable=no-name-in-module
        return collect_oci(compartment_id=kwargs.get('compartment'), output_path=output_path)

    raise ValueError(f"Unknown provider: {provider}")


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
        _dispatch_collect(
            provider, output,
            profile=profile, region=region,
            subscription=subscription, project=project,
            organization=organization, compartment=compartment,
        )

        console.print(f"\n[green]✓ Inventory saved to {output}[/green]")
        console.print(f"[dim]Run 'lm-cloud-inventory calculate -i {output}' to generate license summary[/dim]\n")

    except ImportError as e:
        console.print(f"\n[red]Missing dependency: {e}[/red]")
        console.print(
            f"[yellow]Install required packages with: {escape(_get_install_hint(provider))}[/yellow]"
        )
        console.print("[dim]Run 'lm-cloud-inventory check-deps' to diagnose dependency issues[/dim]")
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

        inventory = _dispatch_collect(
            provider, temp_inventory,
            profile=profile, region=region,
            subscription=subscription, project=project,
            organization=organization, compartment=compartment,
        )

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
        console.print(f"\n[red]Missing dependency: {e}[/red]")
        console.print(
            f"[yellow]Install required packages with: {escape(_get_install_hint(provider))}[/yellow]"
        )
        console.print("[dim]Run 'lm-cloud-inventory check-deps' to diagnose dependency issues[/dim]")
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


@cli.command('check-deps')
@click.option('--provider', '-p',
              type=click.Choice(['aws', 'azure', 'gcp', 'oci']),
              help='Check dependencies for a specific provider (default: all)')
def check_deps(provider: Optional[str]):
    """
    Check if required dependencies are installed.

    Verifies that the SDK packages for each cloud provider are importable
    and reports their versions. Useful for diagnosing installation issues
    in enterprise environments.

    Examples:

      lm-cloud-inventory check-deps

      lm-cloud-inventory check-deps -p azure
    """
    import importlib
    from importlib.metadata import version as pkg_version, PackageNotFoundError

    providers = [provider] if provider else ['aws', 'azure', 'gcp', 'oci']
    has_issues = False

    console.print(f"\n[bold blue]Dependency Check[/bold blue]")
    console.print(f"[dim]Python: {sys.version.split()[0]} ({sys.executable})[/dim]")
    console.print(f"[dim]Platform: {sys.platform}[/dim]\n")
    executable = shutil.which('lmci') or shutil.which('lm-cloud-inventory')
    if executable:
        console.print(f"[dim]CLI: {executable}[/dim]\n")

    for p in providers:
        deps = PROVIDER_DEPENDENCIES[p]
        console.print(
            f"[bold]{p.upper()}[/bold]  (install: {escape(_get_install_hint(p))})"
        )

        all_ok = True
        for pkg_name, import_path in deps:
            installed_version = None
            try:
                installed_version = pkg_version(pkg_name)
            except PackageNotFoundError:
                pass

            if installed_version:
                try:
                    importlib.import_module(import_path)
                    console.print(f"  [green]✓[/green] {pkg_name} {installed_version}")
                except ImportError as e:
                    console.print(
                        f"  [red]✗[/red] {pkg_name} {installed_version} "
                        f"[red](installed but import failed: {e})[/red]"
                    )
                    all_ok = False
                    has_issues = True
            else:
                console.print(f"  [red]✗[/red] {pkg_name} [red]not installed[/red]")
                all_ok = False
                has_issues = True

        if all_ok:
            console.print(f"  [green]All dependencies satisfied.[/green]")
        console.print()

    if has_issues:
        console.print("[yellow]Some dependencies are missing or broken.[/yellow]")
        console.print(
            f"[yellow]Install all providers: {escape(_get_all_install_hint())}[/yellow]\n"
        )
        sys.exit(1)
    else:
        console.print("[green]All checked dependencies are installed and importable.[/green]\n")


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
            console.print(
                "\nRequired IAM permissions:\n"
                "  - resource-explorer-2:Search\n"
                "  - resource-explorer-2:ListResources\n"
                "  - resource-explorer-2:ListViews\n"
                "  - resource-explorer-2:GetView\n"
                "  - sts:GetCallerIdentity\n"
                "\n"
                "For AWS Organizations:\n"
                "  - organizations:ListAccounts\n"
                "  - sts:AssumeRole (for member accounts)\n"
                "\n"
                "Recommended: Use AWS Resource Explorer with an aggregator index.\n"
                "See docs/PERMISSIONS.md for full policy examples.\n"
            )

        elif p == 'azure':
            console.print(
                "\nRequired role: Reader\n"
                "\n"
                "Assign at subscription or management group level:\n"
                '  az role assignment create \\\n'
                '    --assignee <user-or-sp> \\\n'
                '    --role "Reader" \\\n'
                '    --scope "/subscriptions/<sub-id>"\n'
                "\n"
                "See docs/PERMISSIONS.md for full instructions.\n"
            )

        elif p == 'gcp':
            console.print(
                "\nRequired role: roles/cloudasset.viewer\n"
                "\n"
                "Grant access:\n"
                "  gcloud projects add-iam-policy-binding <project> \\\n"
                '    --member="user:you@example.com" \\\n'
                '    --role="roles/cloudasset.viewer"\n'
                "\n"
                "See docs/PERMISSIONS.md for full instructions.\n"
            )

        elif p == 'oci':
            console.print(
                "\nRequired policy:\n"
                "  Allow group <group> to inspect all-resources in tenancy\n"
                "\n"
                "Create policy in OCI Console or via CLI:\n"
                "  oci iam policy create \\\n"
                '    --name "LMInventoryReadOnly" \\\n'
                '    --statements \'["Allow group LMInventory to inspect all-resources in tenancy"]\'\n'
                "\n"
                "See docs/PERMISSIONS.md for full instructions.\n"
            )


def main():
    """Entry point for the CLI."""
    cli()  # pylint: disable=no-value-for-parameter


if __name__ == '__main__':
    main()

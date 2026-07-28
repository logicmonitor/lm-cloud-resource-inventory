# LM Cloud Resource Inventory - Architecture

This document describes the technical architecture for the LogicMonitor Cloud Resource Inventory system.

## Overview

The LM Cloud Resource Inventory system collects cloud resource counts across AWS, Azure, GCP, and OCI for LogicMonitor licensing purposes. The architecture is designed around these principles:

- **Performance**: Use cloud-native inventory APIs for fast collection
- **Security**: Require only read-only permissions
- **Maintainability**: Configuration-driven resource mappings
- **Separation of Concerns**: Decouple data collection from license calculation

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Configuration Layer                             │
│  ┌─────────────────────────┐    ┌─────────────────────────────────────┐ │
│  │  resource_mappings.json │    │       license_rules.json            │ │
│  │  (Resource → Category)  │    │       (SKU → Pricing Rules)         │ │
│  └───────────┬─────────────┘    └──────────────────┬──────────────────┘ │
└──────────────┼─────────────────────────────────────┼────────────────────┘
               │                                     │
               ▼                                     ▼
┌──────────────────────────────────┐    ┌──────────────────────────────────┐
│       Data Collection Layer      │    │       License Calculation        │
│  ┌────────────────────────────┐  │    │  ┌────────────────────────────┐  │
│  │     AWS Collector          │  │    │  │    License Calculator      │  │
│  │  (Resource Explorer API)   │──┼───▶│  │  (Reads raw inventory,     │  │
│  ├────────────────────────────┤  │    │  │   applies rules,           │  │
│  │     Azure Collector        │  │    │  │   outputs summary)         │  │
│  │  (Resource Graph API)      │──┼───▶│  └────────────────────────────┘  │
│  ├────────────────────────────┤  │    └──────────────────────────────────┘
│  │     GCP Collector          │  │                    │
│  │  (Cloud Asset Inventory)   │──┼────────────────────┘
│  ├────────────────────────────┤  │                    ▼
│  │     OCI Collector          │  │    ┌──────────────────────────────────┐
│  │  (Search Service API)      │──┼───▶│        Output Layer              │
│  └────────────────────────────┘  │    │  ┌────────────────────────────┐  │
└──────────────────────────────────┘    │  │  Raw Inventory (JSON)      │  │
                                        │  ├────────────────────────────┤  │
                                        │  │  License Summary (CSV)     │  │
                                        │  └────────────────────────────┘  │
                                        └──────────────────────────────────┘
```

## Cloud-Native Inventory APIs

Each cloud provider offers a centralized inventory API that dramatically improves collection performance:

| Provider | API | Benefit |
|----------|-----|---------|
| **AWS** | [Resource Explorer](https://docs.aws.amazon.com/resource-explorer/latest/userguide/welcome.html) | Single query across all regions and accounts |
| **Azure** | [Resource Graph](https://docs.microsoft.com/en-us/azure/governance/resource-graph/) | KQL queries across all subscriptions |
| **GCP** | [Cloud Asset Inventory](https://cloud.google.com/asset-inventory) | Unified view of all resources |
| **OCI** | [Search Service](https://docs.oracle.com/en-us/iaas/Content/Search/Concepts/searchoverview.htm) | Structured queries across compartments |

### Performance Comparison

| Provider | Legacy Approach | New Approach | Improvement |
|----------|-----------------|--------------|-------------|
| AWS | ~1 hour (per-service, per-region, per-account) | ~2-5 minutes | 10-50x faster |
| Azure | ~30 minutes (per-subscription iteration) | ~1-2 minutes | 10-20x faster |
| GCP | N/A | ~1-2 minutes | N/A |
| OCI | N/A | ~1 minute | N/A |

## Component Details

### 1. Base Collector Interface

All collectors implement a common interface defined in `src/collectors/base.py`:

```python
from abc import ABC, abstractmethod
from typing import Dict, List

class BaseCollector(ABC):
    """Abstract base class for cloud resource collectors."""

    PROVIDER: str = ""

    @abstractmethod
    def collect(self) -> List[Dict]:
        """Collect resources and return standardized inventory."""

    @abstractmethod
    def validate_permissions(self) -> bool:
        """Check if required permissions are available."""

    @abstractmethod
    def get_account_id(self) -> str:
        """Get the current account/subscription/project identifier."""

    def create_inventory_record(self, account_id, region, resource_type, count) -> Dict:
        """Create a standardized inventory record."""

    def save_inventory(self, output_path, inventory=None) -> None:
        """Save inventory to a JSON file."""

    def print_summary(self, inventory=None) -> None:
        """Print a summary of collected resources."""
```

Each collector also tracks `_errors_encountered` to warn users when results may be incomplete due to partial API failures.

### 2. AWS Collector

Uses AWS Resource Explorer `ListResources` API for paginated cross-region inventory.

**Key Features:**
- Uses `ListResources` (not `Search`) to avoid the 1000-result hard limit
- Discovers aggregator vs. local index topology via `list_indexes` (with pagination)
- Supports AWS Organizations: assumes role in each member account and discovers that account's own Resource Explorer indexes independently
- Logs progress every 5000 resources during large scans

**Required Setup:**
- Resource Explorer **must** be enabled in the account (the tool validates this and errors with a link to docs if not found)
- An aggregator index is recommended for cross-region queries; without one, each regional index is queried individually

### 3. Azure Collector

Uses Azure Resource Graph for fast cross-subscription KQL queries.

**Key Features:**
- Full pagination via `skip_token` (Resource Graph returns max 1000 rows per request)
- Batches subscriptions in groups of 200 (Resource Graph API limit)
- Separate VMSS instance query via `ComputeResources` table
- Caches discovered subscriptions after first API call to avoid redundant list operations
- No additional setup required beyond Reader role

**Example Query:**
```kusto
Resources
| summarize count() by type, subscriptionId, location
| order by count_ desc
```

### 4. GCP Collector

Uses Cloud Asset Inventory `SearchAllResources` API.

**Key Features:**
- Supports organization, folder, and project-level scoping
- Auto-discovers project from `GOOGLE_CLOUD_PROJECT` env var or service account credentials file
- Logs progress every 5000 resources during large scans

### 5. OCI Collector

Uses OCI Search Service for structured queries across compartments.

**Key Features:**
- Discovers all compartments recursively with full pagination (`oci.pagination.list_call_get_all_results`)
- Only collects LM-supported resource types: `instance`, `autonomousdatabase`, `volume`, `bootvolume`, `volumereplica`, `bucket`, `drg`
- Aggregates counts by resource type and region across compartments
- Logs compartment scanning progress for large tenancies

### 6. License Calculator

Processes raw inventory data and applies license rules from configuration files.

**Responsibilities:**
- Load resource mappings and license rules from `src/config/`
- Categorize resources into IaaS, PaaS, No-Charge, or Unsupported (former Non-Compute types are No-Charge and excluded from license totals)
- Apply wildcard pattern matching for no-charge resource filtering
- Calculate Hybrid Resource Units (IaaS 1:1, PaaS 7:1 rounded up)
- Generate summary and detailed CSV reports

**Input:** Raw inventory JSON (list of records) from any collector
**Output:** License summary CSV with per-account/region/resource-type breakdown and category totals

## Data Schemas

### Raw Inventory Record

```json
{
  "provider": "aws",
  "account_id": "123456789012",
  "region": "us-east-1",
  "resource_type": "ec2:instance",
  "count": 42,
  "timestamp": "2024-12-22T10:30:00+00:00"
}
```

Resource type formats vary by provider:
- **AWS**: `service:resource-type` (Resource Explorer format, e.g., `ec2:instance`, `lambda:function`)
- **Azure**: `microsoft.provider/resourcetype` (e.g., `microsoft.compute/virtualmachines`)
- **GCP**: `service.googleapis.com/ResourceType` (e.g., `compute.googleapis.com/Instance`)
- **OCI**: Short name (e.g., `instance`, `autonomousdatabase`)

### Resource Mapping Configuration

```json
{
  "aws": {
    "ec2:instance": {
      "category": "IaaS",
      "unit": "Instance"
    },
    "lambda:function": {
      "category": "PaaS",
      "unit": "Function"
    }
  }
}
```

### License Summary CSV Output

```csv
Provider,Account,Category,ResourceType,Region,Count
aws,123456789012,IaaS,ec2:instance,us-east-1,42
aws,123456789012,PaaS,lambda:function,us-east-1,15
...

TOTAL,,IaaS,,,150
TOTAL,,PaaS,,,75
TOTAL,,HYBRID UNITS,,,161
```

## Error Handling

### Permission Errors

Each collector validates permissions before attempting collection:
- Clear error messages indicating missing permissions
- Links to documentation for required roles/policies (`docs/PERMISSIONS.md`)
- `PermissionError` raised with actionable message if validation fails

### API Errors

- Each collector tracks `_errors_encountered` during collection
- Partial results are preserved when individual queries fail
- A warning is logged at the end of collection if any errors occurred: "Results may be incomplete. Re-run with --verbose for details."
- The CLI catches `ImportError` (missing SDK), `PermissionError`, and generic exceptions with appropriate user-facing messages

### Unsupported Resources

Resources not in the mapping configuration are:
- Categorized as "Unsupported"
- Excluded from CSV output and license totals
- Available via `--show-unmapped` flag for review

## Installation and Dependencies

The CLI requires only `click` and `rich` as core dependencies. Cloud provider SDKs are optional:

```bash
pip install lm-cloud-inventory          # Core CLI only
pip install lm-cloud-inventory[aws]     # + AWS SDK (boto3)
pip install lm-cloud-inventory[azure]   # + Azure SDKs
pip install lm-cloud-inventory[gcp]     # + GCP SDK
pip install lm-cloud-inventory[oci]     # + OCI SDK
pip install lm-cloud-inventory[all]     # All providers
```

If a provider SDK is not installed, the tool raises a clear `ImportError` with install instructions when that provider is selected.

## Security Considerations

1. **Read-Only Access**: All APIs are query-only, no write operations
2. **No Credential Storage**: Uses provider credential chains (env vars, config files)
3. **No External Network Calls**: Only communicates with cloud provider APIs
4. **Audit-Friendly Output**: JSON/CSV output can be reviewed before sharing

## CLI Usage

```bash
# Collect inventory for a specific provider
lm-cloud-inventory collect -p aws -o aws_inventory.json
lm-cloud-inventory collect -p azure -s SUB_ID -o azure_inventory.json
lm-cloud-inventory collect -p gcp --project my-project -o gcp_inventory.json
lm-cloud-inventory collect -p oci --compartment OCID -o oci_inventory.json

# AWS with custom region and organization role
lm-cloud-inventory collect -p aws --region us-west-2 --organization MyOrgRole

# Calculate license requirements from collected data
lm-cloud-inventory calculate -i aws_inventory.json -o license_summary.csv

# All-in-one: collect and calculate
lm-cloud-inventory run -p aws -o aws_summary.csv
lm-cloud-inventory run -p azure -d --show-unmapped

# Show required permissions
lm-cloud-inventory permissions -p aws

# Short alias
lmci run -p aws -o summary.csv
```

## Future Considerations

- **Resource Explorer Setup Automation**: Scripts to enable AWS Resource Explorer
- **Cost Estimation**: Add pricing data to license calculations
- **Trend Analysis**: Compare inventory across multiple collection runs
- **Custom Resource Support**: Allow users to add custom resource mappings

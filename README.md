# LM Cloud Resource Inventory

A unified solution for collecting cloud resource counts across AWS, Azure, GCP, and OCI for LogicMonitor licensing purposes.

## Overview

This tool collects resource inventory from cloud providers and calculates LogicMonitor license requirements by categorizing resources into:

- **IaaS** - Virtual machines and compute instances
- **PaaS** - Managed services, containers, serverless functions
- **Non-Compute** - Storage, networking, and other infrastructure resources

## Quick Start

### Installation

```bash
pip install lm-cloud-inventory
```

Or install from source:

```bash
git clone https://github.com/logicmonitor/lm-cloud-resource-inventory.git
cd lm-cloud-resource-inventory
pip install .
```

### Basic Usage

```bash
# Run inventory and calculate licenses
lmci run -p aws -o aws_summary.csv
lmci run -p azure -o azure_summary.csv
lmci run -p gcp -o gcp_summary.csv
lmci run -p oci -o oci_summary.csv
```

---

## CLI Reference

### Global Options

| Option | Description |
|--------|-------------|
| `-v, --verbose` | Enable verbose logging (shows debug info and full tracebacks) |
| `--version` | Show version and exit |
| `--help` | Show help message |

### `run` Command (Recommended)

Collect inventory and calculate licenses in one step. This is the primary command for most users.

```bash
lmci run -p <provider> [options]
```

| Option | Provider | Description |
|--------|----------|-------------|
| `-p, --provider` | All | Cloud provider: `aws`, `azure`, `gcp`, `oci` **(required)** |
| `-o, --output` | All | Output CSV file (default: `license_summary.csv`) |
| `-d, --detailed` | All | Generate detailed CSV with per-region breakdown |
| `--show-unmapped` | All | List resource types not mapped to license categories |
| `--profile` | AWS | AWS CLI profile name |
| `-s, --subscription` | Azure | Subscription ID (can be repeated for multiple) |
| `--project` | GCP | GCP project ID |
| `--compartment` | OCI | OCI compartment OCID |

**Examples:**

```bash
# AWS - basic
lmci run -p aws

# AWS - with named profile
lmci run -p aws --profile production -o aws_prod.csv

# Azure - all subscriptions
lmci run -p azure

# Azure - specific subscriptions
lmci run -p azure -s "sub-id-1" -s "sub-id-2"

# GCP - auto-detect project from credentials
lmci run -p gcp

# GCP - explicit project
lmci run -p gcp --project my-project-id

# OCI - entire tenancy
lmci run -p oci

# OCI - specific compartment
lmci run -p oci --compartment ocid1.compartment.oc1..xxx

# Any provider - with detailed output
lmci run -p aws -d -o detailed_report.csv
```

### `collect` Command

Collect inventory only (saves JSON for later calculation).

```bash
lmci collect -p <provider> [options]
```

| Option | Provider | Description |
|--------|----------|-------------|
| `-p, --provider` | All | Cloud provider **(required)** |
| `-o, --output` | All | Output JSON file (default: `inventory.json`) |
| `--profile` | AWS | AWS CLI profile name |
| `--region` | AWS | AWS region for API calls (default: `us-east-1`) |
| `--organization` | AWS | IAM role name for cross-account access |
| `--organization` | GCP | GCP organization ID for org-wide inventory |
| `-s, --subscription` | Azure | Subscription ID (repeatable) |
| `--project` | GCP | GCP project ID |
| `--compartment` | OCI | OCI compartment OCID |

### `calculate` Command

Calculate licenses from an existing inventory JSON file.

```bash
lmci calculate -i <inventory.json> [options]
```

| Option | Description |
|--------|-------------|
| `-i, --input` | Input inventory JSON file **(required)** |
| `-o, --output` | Output CSV file (default: `license_summary.csv`) |
| `-d, --detailed` | Generate detailed CSV |
| `--show-unmapped` | List unmapped resource types |

### `permissions` Command

Show required permissions for each cloud provider.

```bash
lmci permissions -p aws
lmci permissions -p azure
lmci permissions -p gcp
lmci permissions -p oci
```

---

## Supported Cloud Providers

| Provider | API Used | Performance |
|----------|----------|-------------|
| **AWS** | AWS Resource Explorer | ~2-5 minutes |
| **Azure** | Azure Resource Graph | ~1-2 minutes |
| **GCP** | Cloud Asset Inventory | ~1-2 minutes |
| **OCI** | OCI Search Service | ~1 minute |

For a complete list of supported resources, see [LogicMonitor Cloud Services Documentation](https://www.logicmonitor.com/support/cloud-services-and-resource-units).

### AWS Resource Explorer Limitations

The following AWS services are **not indexed** by AWS Resource Explorer and will not be collected:

| Service | Resource Type |
|---------|---------------|
| CloudSearch | Domain |
| MediaConnect | Flow |
| MediaConvert | Queue |
| OpsWorks | Stack |
| Q Business | Application |
| QuickSight | Dashboard (dataset/datasource are supported) |
| Simple Workflow (SWF) | Domain |
| Application Migration Service | Source Server |
| ElasticTranscoder | Pipeline |

If you have significant usage of these services, contact your LogicMonitor representative for manual inventory assistance.

---

## Requirements

- **Python 3.9+**
- Cloud provider credentials configured
- Read-only permissions (see [docs/PERMISSIONS.md](docs/PERMISSIONS.md))

---

## Credential Setup

Configure credentials for each cloud provider before running the inventory.

### AWS Credentials

**Option 1: AWS CLI (Recommended)**

```bash
# Install AWS CLI and configure
aws configure

# Verify
aws sts get-caller-identity
```

**Option 2: Environment Variables**

```bash
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="us-east-1"
```

**Option 3: Named Profiles**

```bash
# Use a specific profile
lmci run -p aws --profile production
```

**Resources:** [AWS CLI Configuration](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html)

---

### Azure Credentials

**Option 1: Azure CLI (Recommended)**

```bash
# Sign in
az login

# Verify
az account list --output table
```

**Option 2: Service Principal**

```bash
export AZURE_CLIENT_ID="appId"
export AZURE_CLIENT_SECRET="password"
export AZURE_TENANT_ID="tenant"
```

**Resources:** [Azure CLI Authentication](https://learn.microsoft.com/en-us/cli/azure/authenticate-azure-cli)

---

### GCP Credentials

**Option 1: gcloud CLI (Recommended)**

```bash
# Initialize and authenticate
gcloud init
gcloud auth application-default login

# Verify
gcloud config list
```

**Option 2: Service Account Key**

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
```

The tool will automatically extract the `project_id` from the service account JSON file.

**Resources:** [GCP Application Default Credentials](https://cloud.google.com/docs/authentication/application-default-credentials)

---

### OCI Credentials

**Option 1: OCI CLI (Recommended)**

```bash
# Run setup wizard
oci setup config

# Verify
oci iam region list
```

Configuration is stored in `~/.oci/config`.

**Resources:** [OCI CLI Quickstart](https://docs.oracle.com/en-us/iaas/Content/API/SDKDocs/cliinstall.htm)

---

## Running in Cloud Shell

Each cloud provider offers a browser-based shell with credentials pre-configured - **the fastest way to run the inventory tool**.

| Provider | Cloud Shell | Notes |
|----------|-------------|-------|
| AWS | [AWS CloudShell](https://console.aws.amazon.com/cloudshell/) | Python pre-installed, credentials automatic |
| Azure | [Azure Cloud Shell](https://shell.azure.com/) | Python pre-installed, `az` authenticated |
| GCP | [Google Cloud Shell](https://shell.cloud.google.com/) | Python & gcloud pre-installed |
| OCI | [OCI Cloud Shell](https://cloud.oracle.com/?cloudshell=true) | OCI CLI pre-installed |

---

## Output Files

### Summary CSV

The default output includes resource type breakdown by category:

```csv
Provider,Account,Category,ResourceType,Region,Count
aws,123456789012,IaaS,ec2:instance,us-east-1,42
aws,123456789012,IaaS,ec2:instance,us-west-2,15
aws,123456789012,PaaS,lambda:function,us-east-1,28

TOTAL,,IaaS,,,57
TOTAL,,PaaS,,,28
TOTAL,,Non-Compute,,,125
```

### Detailed CSV (with `-d` flag)

Same as summary but saved to a separate `_detailed.csv` file.

### Raw Inventory JSON

The `_inventory.json` file contains raw resource data for analysis:

```json
[
  {
    "provider": "aws",
    "account_id": "123456789012",
    "region": "us-east-1",
    "resource_type": "ec2:instance",
    "count": 42,
    "timestamp": "2024-12-22T10:30:00Z"
  }
]
```

---

## Troubleshooting

### AWS: "Resource Explorer not enabled"

AWS Resource Explorer is required. Enable it in your account:
1. Go to [AWS Resource Explorer Console](https://console.aws.amazon.com/resource-explorer/)
2. Enable Resource Explorer
3. Create an aggregator index for cross-region queries

### AWS: "Access Denied"

```bash
# Verify credentials
aws sts get-caller-identity
```

Check [docs/PERMISSIONS.md](docs/PERMISSIONS.md) for required IAM permissions.

### Azure: "AuthorizationFailed"

```bash
# Verify login
az account show
```

Ensure you have the `Reader` role on the subscription(s).

### GCP: "Permission denied"

```bash
# Verify auth
gcloud auth list
```

Ensure you have the `roles/cloudasset.viewer` role.

### OCI: "NotAuthorizedOrNotFound"

```bash
# Verify config
cat ~/.oci/config
```

Ensure the policy allows: `Allow group <group> to inspect all-resources in tenancy`

### General: "ModuleNotFoundError"

```bash
pip install .
```

---

## Security & Privacy

**Security:**
- Read-only access only - no write/modify/delete operations
- Uses provider credential chains - no credential storage
- Only communicates with cloud provider APIs

**Data Collected:**
- Resource type counts
- Account/subscription identifiers
- Region/location information

**NOT Collected:**
- Resource names or IDs
- Resource content or data
- Configuration details
- Credentials or secrets

---

## Documentation

- [Required Permissions](docs/PERMISSIONS.md)
- [Architecture](docs/ARCHITECTURE.md)
- [LogicMonitor Cloud Services](https://www.logicmonitor.com/support/cloud-services-and-resource-units)

---

## Support

- **Pre-sales:** Contact your LogicMonitor Sales Engineer
- **Customers:** Contact your Customer Success Manager

---

## License

MIT License - See [LICENSE](LICENSE) file for details.

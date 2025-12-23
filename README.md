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
# Clone the repository
git clone https://github.com/logicmonitor/lm-cloud-resource-inventory.git
cd lm-cloud-resource-inventory

# Install dependencies
pip install -r requirements.txt
```

### Basic Usage

```bash
# Collect and calculate in one step
python -m src.cli run -p aws -o aws_summary.csv
python -m src.cli run -p azure -o azure_summary.csv
python -m src.cli run -p gcp -o gcp_summary.csv
python -m src.cli run -p oci -o oci_summary.csv

# Or collect and calculate separately
python -m src.cli collect -p aws -o aws_inventory.json
python -m src.cli calculate -i aws_inventory.json -o aws_summary.csv
```

## Supported Cloud Providers

| Provider | API Used | Performance |
|----------|----------|-------------|
| **AWS** | AWS Resource Explorer | ~2-5 minutes |
| **Azure** | Azure Resource Graph | ~1-2 minutes |
| **GCP** | Cloud Asset Inventory | ~1-2 minutes |
| **OCI** | OCI Search Service | ~1 minute |

For a complete list of supported resources, see [docs/SUPPORTED_RESOURCES.md](https://www.logicmonitor.com/support/cloud-services-and-resource-units).

### AWS Resource Explorer Limitations

The following AWS services are **not supported** by AWS Resource Explorer and will not be collected:

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

These are generally legacy services or very new services. If you have significant usage of these services, please contact your LogicMonitor representative for manual inventory assistance.

---

## Requirements

- **Python 3.9+**
- Cloud provider credentials configured (see setup instructions below)
- Read-only permissions (see [docs/PERMISSIONS.md](docs/PERMISSIONS.md))

---

## Credential Setup

Before running the inventory tool, you must configure credentials for each cloud provider you want to collect from.

### AWS Credentials

**Option 1: AWS CLI (Recommended)**

1. Install the AWS CLI: [AWS CLI Installation Guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)

2. Configure credentials:
   ```bash
   aws configure
   ```
   Enter your Access Key ID, Secret Access Key, and default region when prompted.

3. Verify setup:
   ```bash
   aws sts get-caller-identity
   ```

**Option 2: Environment Variables**

```bash
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="us-east-1"
```

**Option 3: Named Profiles**

If you have multiple AWS accounts, use named profiles in `~/.aws/credentials`:

```ini
[default]
aws_access_key_id = YOUR_DEFAULT_KEY
aws_secret_access_key = YOUR_DEFAULT_SECRET

[production]
aws_access_key_id = YOUR_PROD_KEY
aws_secret_access_key = YOUR_PROD_SECRET
```

Then run with: `python -m src.cli run -p aws --profile production`

**AWS Resources:**
- [Configuration and credential file settings](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html)
- [Named profiles](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-profiles.html)
- [IAM credentials best practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)

---

### Azure Credentials

**Option 1: Azure CLI (Recommended)**

1. Install the Azure CLI: [Azure CLI Installation Guide](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli)

2. Sign in to Azure:
   ```bash
   az login
   ```
   A browser window will open for authentication.

3. Verify setup and list subscriptions:
   ```bash
   az account list --output table
   ```

4. (Optional) Set a default subscription:
   ```bash
   az account set --subscription "Your Subscription Name"
   ```

**Option 2: Service Principal**

For automation or when browser login isn't available:

1. Create a service principal:
   ```bash
   az ad sp create-for-rbac --name "LMInventory" --role "Reader" \
     --scopes /subscriptions/<subscription-id>
   ```

2. Set environment variables with the output:
   ```bash
   export AZURE_CLIENT_ID="appId-from-output"
   export AZURE_CLIENT_SECRET="password-from-output"
   export AZURE_TENANT_ID="tenant-from-output"
   ```

**Azure Resources:**
- [Sign in with Azure CLI](https://learn.microsoft.com/en-us/cli/azure/authenticate-azure-cli)
- [Create a service principal](https://learn.microsoft.com/en-us/cli/azure/create-an-azure-service-principal-azure-cli)
- [Azure RBAC built-in roles](https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles)

---

### GCP Credentials

**Option 1: gcloud CLI (Recommended)**

1. Install the gcloud CLI: [Google Cloud CLI Installation Guide](https://cloud.google.com/sdk/docs/install)

2. Initialize and authenticate:
   ```bash
   gcloud init
   ```
   Follow the prompts to select your project and authenticate.

3. Set application default credentials:
   ```bash
   gcloud auth application-default login
   ```

4. Verify setup:
   ```bash
   gcloud config list
   ```

**Option 2: Service Account Key**

For automation or non-interactive use:

1. Create a service account in the [GCP Console](https://console.cloud.google.com/iam-admin/serviceaccounts)

2. Grant the **Cloud Asset Viewer** role

3. Create and download a JSON key file

4. Set the environment variable:
   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
   ```

**GCP Resources:**
- [Installing Google Cloud CLI](https://cloud.google.com/sdk/docs/install)
- [Application Default Credentials](https://cloud.google.com/docs/authentication/application-default-credentials)
- [Creating service account keys](https://cloud.google.com/iam/docs/keys-create-delete)

---

### OCI Credentials

**Option 1: OCI CLI Configuration (Recommended)**

1. Install the OCI CLI: [OCI CLI Installation Guide](https://docs.oracle.com/en-us/iaas/Content/API/SDKDocs/cliinstall.htm)

2. Run the setup wizard:
   ```bash
   oci setup config
   ```
   This will prompt you for:
   - User OCID (found in OCI Console → Profile → User Settings)
   - Tenancy OCID (found in OCI Console → Profile → Tenancy)
   - Region identifier (e.g., `us-phoenix-1`)
   - Generate a new API key pair (recommended)

3. Upload the public key to your OCI user profile

4. Verify setup:
   ```bash
   oci iam region list
   ```

**Configuration File Location:** `~/.oci/config`

Example config file:

```ini
[DEFAULT]
user=ocid1.user.oc1..aaaaaaaxxxxxxxxxx
fingerprint=aa:bb:cc:dd:ee:ff:00:11:22:33:44:55:66:77:88:99
tenancy=ocid1.tenancy.oc1..aaaaaaaxxxxxxxxxx
region=us-phoenix-1
key_file=~/.oci/oci_api_key.pem
```

**OCI Resources:**
- [OCI CLI Quickstart](https://docs.oracle.com/en-us/iaas/Content/API/SDKDocs/cliinstall.htm)
- [Required Keys and OCIDs](https://docs.oracle.com/en-us/iaas/Content/API/Concepts/apisigningkey.htm)
- [Managing API Keys](https://docs.oracle.com/en-us/iaas/Content/Identity/Tasks/managingcredentials.htm)

---

## Running in Cloud Shell

Each cloud provider offers a browser-based shell with credentials pre-configured. **This is the fastest way to run the inventory tool** - no local setup required.

| Provider | Cloud Shell | Notes |
|----------|-------------|-------|
| AWS | [AWS CloudShell](https://console.aws.amazon.com/cloudshell/) | Python pre-installed, credentials automatic |
| Azure | [Azure Cloud Shell](https://shell.azure.com/) | Python pre-installed, `az` authenticated |
| GCP | [Google Cloud Shell](https://shell.cloud.google.com/) | Python & gcloud pre-installed |
| OCI | [OCI Cloud Shell](https://cloud.oracle.com/?cloudshell=true) | OCI CLI pre-installed |

---

## Detailed Usage

### AWS

```bash
# Single account
python -m src.cli run -p aws -o aws_summary.csv

# With specific profile
python -m src.cli run -p aws --profile myprofile -o aws_summary.csv

# AWS Organizations (multi-account)
python -m src.cli collect -p aws --organization OrganizationAccountAccessRole -o aws_inventory.json
```

**Required Permissions:**
- `resource-explorer-2:Search`, `resource-explorer-2:ListViews` (if using Resource Explorer)
- Or `ReadOnlyAccess` policy for fallback mode

**Note:** For best performance, enable [AWS Resource Explorer](https://docs.aws.amazon.com/resource-explorer/) with an aggregator index.

### Azure

```bash
# All subscriptions
python -m src.cli run -p azure -o azure_summary.csv

# Specific subscriptions
python -m src.cli run -p azure -s "subscription-id-1" -s "subscription-id-2" -o azure_summary.csv
```

**Required Permissions:** `Reader` role at subscription or management group level.

### GCP

```bash
# Single project
python -m src.cli run -p gcp --project my-project -o gcp_summary.csv

# Organization-wide
python -m src.cli run -p gcp --organization 123456789 -o gcp_summary.csv
```

**Required Permissions:** `roles/cloudasset.viewer`

### OCI

```bash
# Tenancy-wide
python -m src.cli run -p oci -o oci_summary.csv

# Specific compartment
python -m src.cli run -p oci --compartment ocid1.compartment.oc1..xxx -o oci_summary.csv
```

**Required Permissions:** `Allow group <group> to inspect all-resources in tenancy`

---

## Output Files

### Summary CSV

```csv
Provider,Category,Count
aws,IaaS,150
aws,PaaS,75
aws,Non-Compute,425
```

### Detailed CSV (with `-d` flag)

```csv
Provider,Account,Region,ResourceType,Category,Count
aws,123456789012,us-east-1,AWS::EC2::Instance,IaaS,42
aws,123456789012,us-east-1,AWS::Lambda::Function,PaaS,15
```

### Raw Inventory JSON

```json
[
  {
    "provider": "aws",
    "account_id": "123456789012",
    "region": "us-east-1",
    "resource_type": "AWS::EC2::Instance",
    "count": 42,
    "timestamp": "2024-12-22T10:30:00Z"
  }
]
```

---

## Architecture

The tool is designed with separation of concerns:

1. **Data Collection** - Provider-specific collectors gather resource counts
2. **Configuration** - JSON files define resource-to-category mappings
3. **Calculation** - License calculator processes inventory and applies rules
4. **Output** - Unified CSV/JSON output format

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed technical documentation.

---

## Configuration

### Resource Mappings

Resource type to category mappings are defined in `config/resource_mappings.json`. Add new resource types here without modifying code.

### License Rules

Calculation rules are defined in `config/license_rules.json`, including:
- Category definitions
- No-charge resources
- Special counting rules

---

## Kubernetes Resource Counting

For Kubernetes-based services (EKS, AKS, GKE), LogicMonitor counts K8s pods as the billable unit when using LM Container monitoring.

To get pod counts for each cluster:

```bash
kubectl get pods --all-namespaces --no-headers -o custom-columns=Type:kind | sort | uniq -c
```

---

## CLI Reference

```bash
# Show all commands
python -m src.cli --help

# Collect resources
python -m src.cli collect --help

# Calculate licenses
python -m src.cli calculate --help

# Run both steps
python -m src.cli run --help

# Show required permissions
python -m src.cli permissions -p aws
```

---

## Troubleshooting

### AWS: "Resource Explorer not enabled"

The tool will fall back to direct API calls (slower). For best performance:
1. Enable AWS Resource Explorer in your account
2. Create an aggregator index for cross-region queries

### AWS: "Access Denied" or "UnauthorizedAccess"

1. Verify your credentials are configured:
   ```bash
   aws sts get-caller-identity
   ```

2. Check that your IAM user/role has the required permissions (see [docs/PERMISSIONS.md](docs/PERMISSIONS.md))

### Azure: "AuthorizationFailed"

1. Ensure you're logged in:
   ```bash
   az account show
   ```

2. Verify you have the `Reader` role assigned:
   ```bash
   az role assignment list --assignee $(az account show --query user.name -o tsv)
   ```

### GCP: "Permission denied"

1. Verify authentication:
   ```bash
   gcloud auth list
   ```

2. Check Cloud Asset Viewer role:
   ```bash
   gcloud projects get-iam-policy <project-id> --filter="bindings.role:cloudasset.viewer"
   ```

### OCI: "NotAuthorizedOrNotFound"

1. Verify your config file:
   ```bash
   cat ~/.oci/config
   ```

2. Check policy:
   ```bash
   oci iam policy list --compartment-id <tenancy-ocid> --all
   ```

### General: "ModuleNotFoundError"

Install the required dependencies:
```bash
pip install -r requirements.txt
```

---

## Security

- **Read-only access only** - No write, modify, or delete operations
- **No credential storage** - Uses provider credential chains
- **No external network calls** - Only communicates with cloud provider APIs
- **Audit-friendly output** - Review JSON/CSV before sharing

---

## Data Privacy

**The tool collects:**
- Resource type counts
- Account/subscription identifiers
- Region/location information

**The tool does NOT collect:**
- Resource names or IDs (unless using detailed mode)
- Resource content or data
- Configuration details
- Credentials or secrets

---

## Support

For questions or issues:
- **Pre-sales:** Contact your LogicMonitor Sales Engineer
- **Customers:** Contact your Customer Success Manager

---

## Documentation

- [Supported Resources](docs/SUPPORTED_RESOURCES.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Required Permissions](docs/PERMISSIONS.md)
- [LogicMonitor Cloud Services Documentation](https://www.logicmonitor.com/support/cloud-services-and-resource-units)

---

## License

MIT License - See LICENSE file for details.

# Required Permissions

This document details the minimum permissions required to run the LM Cloud Resource Inventory collectors for each cloud provider.

## Overview

All collectors require **read-only** access to inventory/asset APIs. No write, modify, or delete permissions are needed.

| Provider | Required Role/Permission | Scope |
|----------|--------------------------|-------|
| AWS | AWSResourceExplorerReadOnlyAccess | Organization or Account |
| Azure | Reader | Subscription(s) |
| GCP | Cloud Asset Viewer | Organization or Project |
| OCI | Inspect All Resources | Tenancy or Compartment |

---

## Amazon Web Services (AWS)

### About AWS Resource Explorer

AWS Resource Explorer is **automatically available** in all AWS accounts. No manual setup is required - you can start searching for resources immediately with the appropriate permissions.

For more details, see: [Setting up and configuring Resource Explorer](https://docs.aws.amazon.com/resource-explorer/latest/userguide/getting-started-setting-up.html)

---

### Required Permissions

**Option 1: AWS Managed Policy (Recommended)**

Attach the AWS managed policy **`AWSResourceExplorerReadOnlyAccess`** to your IAM user or role. This is the simplest approach.

```bash
# Attach managed policy to a user
aws iam attach-user-policy \
  --user-name <username> \
  --policy-arn arn:aws:iam::aws:policy/AWSResourceExplorerReadOnlyAccess

# Attach managed policy to a role
aws iam attach-role-policy \
  --role-name <role-name> \
  --policy-arn arn:aws:iam::aws:policy/AWSResourceExplorerReadOnlyAccess
```

**Option 2: Custom IAM Policy**

If you prefer a custom policy with minimal permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "ResourceExplorerReadOnly",
            "Effect": "Allow",
            "Action": [
                "resource-explorer-2:Search",
                "resource-explorer-2:ListResources",
                "resource-explorer-2:GetView",
                "resource-explorer-2:ListViews",
                "resource-explorer-2:GetIndex",
                "resource-explorer-2:ListIndexes"
            ],
            "Resource": "*"
        },
        {
            "Sid": "GetCallerIdentity",
            "Effect": "Allow",
            "Action": [
                "sts:GetCallerIdentity"
            ],
            "Resource": "*"
        }
    ]
}
```

---

### Optional: Cross-Region Search

By default, Resource Explorer searches resources in the current region. For **cross-region search** (searching all regions from a single query), you can optionally configure an aggregator index.

**To enable cross-region search:**

1. Open the [AWS Resource Explorer Console](https://console.aws.amazon.com/resource-explorer/)
2. Go to **Settings**
3. Choose **Enable cross-Region search**
4. Select the region for your aggregator index
5. Click **Enable cross-Region search in all Regions**

This is optional but recommended for large multi-region environments.

---

### For AWS Organizations (Multi-Account)

If collecting resources across multiple accounts in an AWS Organization, you need additional permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "ResourceExplorerReadOnly",
            "Effect": "Allow",
            "Action": [
                "resource-explorer-2:Search",
                "resource-explorer-2:ListResources",
                "resource-explorer-2:GetView",
                "resource-explorer-2:ListViews",
                "resource-explorer-2:GetIndex",
                "resource-explorer-2:ListIndexes"
            ],
            "Resource": "*"
        },
        {
            "Sid": "OrganizationsReadOnly",
            "Effect": "Allow",
            "Action": [
                "organizations:ListAccounts",
                "organizations:DescribeOrganization",
                "organizations:ListAccountsForParent"
            ],
            "Resource": "*"
        },
        {
            "Sid": "AssumeRoleInMemberAccounts",
            "Effect": "Allow",
            "Action": [
                "sts:AssumeRole"
            ],
            "Resource": "arn:aws:iam::*:role/LMInventoryReadOnly"
        }
    ]
}
```

**Note:** Each member account must have a role (`LMInventoryReadOnly`) that can be assumed by the management account.

---

### How to Apply Permissions

**Option 1: AWS Console**

1. Go to **IAM** → **Users** or **Roles**
2. Select the user or role
3. Click **Add permissions** → **Attach policies directly**
4. Search for `AWSResourceExplorerReadOnlyAccess`
5. Select it and click **Add permissions**

**Option 2: AWS CLI**

```bash
# Attach managed policy to user
aws iam attach-user-policy \
  --user-name <username> \
  --policy-arn arn:aws:iam::aws:policy/AWSResourceExplorerReadOnlyAccess
```

**Option 3: Custom Policy via CLI**

1. Save the custom policy JSON to a file (e.g., `lm-inventory-policy.json`)
2. Create the policy:
   ```bash
   aws iam create-policy \
     --policy-name LMInventoryReadOnly \
     --policy-document file://lm-inventory-policy.json
   ```
3. Attach to a user:
   ```bash
   aws iam attach-user-policy \
     --user-name <username> \
     --policy-arn arn:aws:iam::<account-id>:policy/LMInventoryReadOnly
   ```

---

## Microsoft Azure

### Required Role

The built-in **Reader** role provides all necessary permissions. No additional setup is required.

### Scope Options

| Scope | Use Case | Command Scope Value |
|-------|----------|---------------------|
| Management Group | All subscriptions in the group | `/providers/Microsoft.Management/managementGroups/<mg-id>` |
| Subscription | Single subscription | `/subscriptions/<subscription-id>` |
| Resource Group | Specific resource group only | `/subscriptions/<sub-id>/resourceGroups/<rg-name>` |

---

### How to Apply

**Option 1: Azure Portal**

1. Navigate to the subscription or management group
2. Go to **Access control (IAM)** in the left menu
3. Click **+ Add** → **Add role assignment**
4. Select **Reader** role
5. Click **Next**
6. Select **User, group, or service principal**
7. Search for and select the user or service principal
8. Click **Review + assign**

**Option 2: Azure CLI**

```bash
# Assign Reader role at subscription level
az role assignment create \
  --assignee "<user-email-or-object-id>" \
  --role "Reader" \
  --scope "/subscriptions/<subscription-id>"

# Assign Reader role at management group level (all subscriptions)
az role assignment create \
  --assignee "<user-email-or-object-id>" \
  --role "Reader" \
  --scope "/providers/Microsoft.Management/managementGroups/<mg-id>"
```

**Option 3: Azure PowerShell**

```powershell
# Assign Reader role at subscription level
New-AzRoleAssignment `
  -SignInName "<user-email>" `
  -RoleDefinitionName "Reader" `
  -Scope "/subscriptions/<subscription-id>"
```

---

### Service Principal (For Automation)

If using a service principal instead of user credentials:

```bash
# Create service principal with Reader role
az ad sp create-for-rbac \
  --name "LMInventoryReader" \
  --role "Reader" \
  --scopes "/subscriptions/<subscription-id>"
```

**Output example:**
```json
{
  "appId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "displayName": "LMInventoryReader",
  "password": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "tenant": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

Save these values securely. You'll need them for the environment variables:
- `AZURE_CLIENT_ID` = appId
- `AZURE_CLIENT_SECRET` = password
- `AZURE_TENANT_ID` = tenant

---

## Google Cloud Platform (GCP)

### Prerequisites

The **Cloud Asset API** must be enabled in your project.

**Enable the API:**
```bash
gcloud services enable cloudasset.googleapis.com --project <project-id>
```

Or enable via the [GCP Console](https://console.cloud.google.com/apis/library/cloudasset.googleapis.com).

---

### Required Role

The predefined **Cloud Asset Viewer** role (`roles/cloudasset.viewer`) provides all necessary permissions.

### Scope Options

| Scope | Use Case |
|-------|----------|
| Organization | All projects in the organization |
| Folder | All projects in a folder |
| Project | Single project |

---

### How to Apply

**Option 1: Google Cloud Console**

1. Go to **IAM & Admin** → **IAM**
2. Click **+ Grant Access**
3. In **New principals**, enter the user or service account email
4. In **Select a role**, choose **Cloud Asset** → **Cloud Asset Viewer**
5. Click **Save**

**Option 2: gcloud CLI**

```bash
# Grant at project level
gcloud projects add-iam-policy-binding <project-id> \
  --member="user:<user-email>" \
  --role="roles/cloudasset.viewer"

# Grant at organization level
gcloud organizations add-iam-policy-binding <org-id> \
  --member="user:<user-email>" \
  --role="roles/cloudasset.viewer"

# Grant to a service account
gcloud projects add-iam-policy-binding <project-id> \
  --member="serviceAccount:<sa-email>" \
  --role="roles/cloudasset.viewer"
```

---

### Service Account (For Automation)

```bash
# Create service account
gcloud iam service-accounts create lm-inventory-reader \
  --display-name="LM Inventory Reader" \
  --project=<project-id>

# Grant Cloud Asset Viewer role
gcloud projects add-iam-policy-binding <project-id> \
  --member="serviceAccount:lm-inventory-reader@<project-id>.iam.gserviceaccount.com" \
  --role="roles/cloudasset.viewer"

# Create and download key file
gcloud iam service-accounts keys create ~/lm-inventory-key.json \
  --iam-account=lm-inventory-reader@<project-id>.iam.gserviceaccount.com
```

Set the environment variable to use the key:
```bash
export GOOGLE_APPLICATION_CREDENTIALS=~/lm-inventory-key.json
```

---

## Oracle Cloud Infrastructure (OCI)

### Required Policy

Create a policy that grants `inspect` permission on all resources.

### Policy Statements

**Tenancy-wide access:**
```
Allow group LMInventoryReaders to inspect all-resources in tenancy
```

**Compartment-scoped access:**
```
Allow group LMInventoryReaders to inspect all-resources in compartment <compartment-name>
```

---

### How to Apply

**Option 1: OCI Console**

1. Go to **Identity & Security** → **Policies**
2. Ensure you're in the **root compartment** (for tenancy-wide policies)
3. Click **Create Policy**
4. Enter:
   - **Name:** `LMInventoryReadOnly`
   - **Description:** `Read-only access for LM resource inventory`
   - **Policy Builder:** Switch to **Manual Editor**
   - **Statement:** `Allow group LMInventoryReaders to inspect all-resources in tenancy`
5. Click **Create**

**Option 2: OCI CLI**

```bash
oci iam policy create \
  --compartment-id <tenancy-ocid> \
  --name "LMInventoryReadOnly" \
  --description "Read-only access for LM resource inventory" \
  --statements '["Allow group LMInventoryReaders to inspect all-resources in tenancy"]'
```

---

### User and Group Setup

**Step 1: Create the group**

```bash
oci iam group create \
  --name "LMInventoryReaders" \
  --description "LM Inventory Read Access"
```

**Step 2: Add users to the group**

```bash
oci iam group add-user \
  --group-id <group-ocid> \
  --user-id <user-ocid>
```

---

### API Key Setup

For running the collector, you'll need an API key:

**Option 1: OCI Console**

1. Go to **Profile** (top-right) → **User Settings**
2. Under **Resources**, click **API Keys**
3. Click **Add API Key**
4. Select **Generate API Key Pair**
5. Click **Download Private Key** and save securely
6. Click **Add**
7. Copy the **Configuration File Preview** to `~/.oci/config`

**Option 2: OCI CLI**

```bash
oci setup config
```

Follow the prompts to enter your User OCID, Tenancy OCID, Region, and generate an API key.

---

## Security Best Practices

1. **Use temporary credentials** where possible (IAM roles, managed identities)
2. **Rotate credentials regularly** for long-term access keys
3. **Scope permissions narrowly** - use compartment/subscription limits when possible
4. **Audit access** - review who has inventory read access periodically
5. **Review output before sharing** - JSON/CSV files may contain account IDs and resource names
6. **Delete credentials after use** - if created specifically for this inventory

---

## Troubleshooting

### AWS: "AccessDeniedException"

```bash
# Verify current identity
aws sts get-caller-identity

# Verify Resource Explorer permissions
aws resource-explorer-2 list-indexes
```

**Resolution:** Ensure the `AWSResourceExplorerReadOnlyAccess` policy is attached to your user or role.

---

### Azure: "AuthorizationFailed"

```bash
# Verify current identity
az account show

# List your role assignments
az role assignment list --assignee $(az ad signed-in-user show --query id -o tsv)
```

**Resolution:** Ensure the Reader role is assigned at the appropriate scope.

---

### GCP: "Permission 'cloudasset.assets.searchAllResources' denied"

```bash
# Verify current identity
gcloud auth list

# Check if Cloud Asset API is enabled
gcloud services list --enabled --filter="name:cloudasset"

# Check IAM bindings
gcloud projects get-iam-policy <project-id> \
  --flatten="bindings[].members" \
  --filter="bindings.role:cloudasset.viewer"
```

**Resolution:** Ensure the Cloud Asset API is enabled and the Cloud Asset Viewer role is assigned.

---

### OCI: "NotAuthorizedOrNotFound"

```bash
# Verify your config
cat ~/.oci/config

# Test API connectivity
oci iam region list

# Check group memberships
oci iam group list --all
```

**Resolution:** Verify your user is in the `LMInventoryReaders` group and the policy is in the root compartment.

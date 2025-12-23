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
└──────────────────────────────────┘    │  │  Raw Inventory (JSON/CSV)  │  │
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

All collectors implement a common interface:

```python
from abc import ABC, abstractmethod
from typing import Dict, List

class BaseCollector(ABC):
    """Abstract base class for cloud resource collectors."""
    
    @abstractmethod
    def collect(self) -> List[Dict]:
        """
        Collect resources and return standardized inventory.
        
        Returns:
            List of resource records with schema:
            {
                "provider": str,          # aws, azure, gcp, oci
                "account_id": str,        # Account/Subscription/Project ID
                "region": str,            # Resource region/location
                "resource_type": str,     # Provider-specific resource type
                "count": int,             # Number of resources
                "timestamp": str          # ISO 8601 timestamp
            }
        """
        pass
    
    @abstractmethod
    def validate_permissions(self) -> bool:
        """Check if required permissions are available."""
        pass
```

### 2. AWS Collector

Uses AWS Resource Explorer for fast cross-region, cross-account inventory.

**Key Features:**
- Single API call to search all resource types
- Supports AWS Organizations for multi-account scenarios
- Falls back to direct API calls if Resource Explorer is not enabled

**Required Setup:**
- Resource Explorer must be enabled in the organization/account
- An aggregator index should be created for cross-region queries

### 3. Azure Collector

Uses Azure Resource Graph for fast cross-subscription queries.

**Key Features:**
- KQL queries for efficient resource counting
- Groups resources by type and subscription
- No additional setup required beyond Reader role

**Example Query:**
```kusto
Resources
| summarize count() by type, subscriptionId, location
```

### 4. GCP Collector

Uses Cloud Asset Inventory API for unified resource view.

**Key Features:**
- Single API call for organization-wide inventory
- Supports project-level scoping
- Real-time asset data

### 5. OCI Collector

Uses OCI Search Service for structured queries.

**Key Features:**
- Structured Query Language for resource discovery
- Supports compartment hierarchy traversal
- Tenancy-wide resource visibility

### 6. License Calculator

Processes raw inventory data and applies license rules.

**Responsibilities:**
- Load resource mappings configuration
- Categorize resources (IaaS, PaaS, Non-Compute)
- Apply any special counting rules
- Generate summary report

**Input:** Raw inventory JSON from any collector
**Output:** License summary CSV with category totals

## Data Schemas

### Raw Inventory Record

```json
{
  "provider": "aws",
  "account_id": "123456789012",
  "region": "us-east-1",
  "resource_type": "AWS::EC2::Instance",
  "count": 42,
  "timestamp": "2024-12-22T10:30:00Z"
}
```

### Resource Mapping Configuration

```json
{
  "aws": {
    "AWS::EC2::Instance": {
      "category": "IaaS",
      "unit": "Instance",
      "notes": "Virtual machines"
    },
    "AWS::Lambda::Function": {
      "category": "PaaS",
      "unit": "Function",
      "notes": "Serverless functions"
    }
  }
}
```

### License Summary Output

```csv
Provider,Category,Count
aws,IaaS,150
aws,PaaS,75
aws,Non-Compute,425
azure,IaaS,200
azure,PaaS,50
azure,Non-Compute,300
```

## Error Handling

### Permission Errors

Each collector validates permissions before attempting collection:
- Clear error messages indicating missing permissions
- Links to documentation for required roles/policies
- Graceful degradation where possible

### API Errors

- Retry logic with exponential backoff
- Partial results saved on failure
- Detailed error logging for troubleshooting

### Unsupported Resources

Resources not in the mapping configuration are:
- Logged as warnings
- Included in a separate "unsupported" category
- Not counted toward license totals

## Security Considerations

1. **Read-Only Access**: All APIs are query-only, no write operations
2. **No Credential Storage**: Uses provider credential chains (env vars, config files)
3. **No External Network Calls**: Only communicates with cloud provider APIs
4. **Audit-Friendly Output**: JSON/CSV output can be reviewed before sharing

## Deployment Options

| Option | Use Case | Prerequisites |
|--------|----------|---------------|
| **Python Script** | Users with Python installed | Python 3.9+, pip install |
| **Cloud Shell** | Quick browser-based execution | Cloud account access |

## CLI Usage

```bash
# Collect inventory for a specific provider
python -m lm_inventory collect --provider aws --output aws_inventory.json
python -m lm_inventory collect --provider azure --output azure_inventory.json

# Calculate license requirements from collected data
python -m lm_inventory calculate --input aws_inventory.json --output license_summary.csv

# All-in-one: collect and calculate
python -m lm_inventory run --provider aws --output license_summary.csv

# Show detailed resource breakdown
python -m lm_inventory run --provider aws --detailed
```

## Future Considerations

- **Resource Explorer Setup Automation**: Scripts to enable AWS Resource Explorer
- **Cost Estimation**: Add pricing data to license calculations
- **Trend Analysis**: Compare inventory across multiple collection runs
- **Custom Resource Support**: Allow users to add custom resource mappings


"""Cloud resource collectors for AWS, Azure, GCP, and OCI."""

from .base import BaseCollector
from .aws_collector import AWSCollector, collect_aws
from .azure_collector import AzureCollector, collect_azure
from .gcp_collector import GCPCollector, collect_gcp
from .oci_collector import OCICollector, collect_oci

__all__ = [
    "BaseCollector",
    "AWSCollector",
    "AzureCollector", 
    "GCPCollector",
    "OCICollector",
    "collect_aws",
    "collect_azure",
    "collect_gcp",
    "collect_oci",
]

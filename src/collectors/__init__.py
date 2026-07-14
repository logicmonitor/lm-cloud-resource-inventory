"""Cloud resource collectors for AWS, Azure, GCP, and OCI.

Collector modules are imported lazily so that only the SDK dependencies
for the requested provider need to be installed.
"""

from .base import BaseCollector

# pylint: disable=undefined-all-variable
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
# pylint: enable=undefined-all-variable
_LAZY_IMPORTS = {
    "AWSCollector": (".aws_collector", "AWSCollector"),
    "collect_aws": (".aws_collector", "collect_aws"),
    "AzureCollector": (".azure_collector", "AzureCollector"),
    "collect_azure": (".azure_collector", "collect_azure"),
    "GCPCollector": (".gcp_collector", "GCPCollector"),
    "collect_gcp": (".gcp_collector", "collect_gcp"),
    "OCICollector": (".oci_collector", "OCICollector"),
    "collect_oci": (".oci_collector", "collect_oci"),
}


def __getattr__(name: str):
    if name in _LAZY_IMPORTS:
        module_path, attr = _LAZY_IMPORTS[name]
        import importlib
        module = importlib.import_module(module_path, package=__name__)
        value = getattr(module, attr)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

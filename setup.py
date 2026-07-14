"""Setup script for LM Cloud Resource Inventory."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="lm-cloud-inventory",
    use_scm_version=True,
    author="LogicMonitor",
    author_email="support@logicmonitor.com",
    description="Cloud resource inventory collection for LogicMonitor licensing",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/logicmonitor/lm-cloud-resource-inventory",
    packages=find_packages(include=["src", "src.*"]),
    package_data={"src.config": ["*.json"]},
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.9",
    install_requires=[
        "click>=8.3.1",
        "rich>=14.2.0",
    ],
    extras_require={
        "aws": ["boto3>=1.42.15"],
        "azure": [
            "azure-identity>=1.25.1",
            "azure-mgmt-resourcegraph>=8.0.1",
            "azure-mgmt-resource>=24.0.0",
        ],
        "gcp": ["google-cloud-asset>=4.1.0"],
        "oci": ["oci>=2.164.2"],
        "all": [
            "boto3>=1.42.15",
            "azure-identity>=1.25.1",
            "azure-mgmt-resourcegraph>=8.0.1",
            "azure-mgmt-resource>=24.0.0",
            "google-cloud-asset>=4.1.0",
            "oci>=2.164.2",
        ],
    },
    entry_points={
        "console_scripts": [
            "lm-cloud-inventory=src.cli:main",
            "lmci=src.cli:main",
        ],
    },
)

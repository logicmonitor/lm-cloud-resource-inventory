"""Setup script for LM Cloud Resource Inventory."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="lm-cloud-inventory",
    use_scm_version=True,
    setup_requires=["setuptools-scm"],
    author="LogicMonitor",
    author_email="support@logicmonitor.com",
    description="Cloud resource inventory collection for LogicMonitor licensing",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/logicmonitor/lm-cloud-resource-inventory",
    packages=find_packages(include=["src", "src.*"]),
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
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "lm-cloud-inventory=src.cli:main",
            "lmci=src.cli:main",
        ],
    },
)

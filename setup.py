"""Setup script for LM Cloud Resource Inventory."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="lm-cloud-inventory",
    version="2.0.0",
    author="LogicMonitor",
    author_email="support@logicmonitor.com",
    description="Cloud resource inventory collection for LogicMonitor licensing",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/logicmonitor/lm-cloud-resource-inventory",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    classifiers=[
        "Development Status :: 4 - Beta",
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
            "lm-inventory=cli:main",
        ],
    },
)

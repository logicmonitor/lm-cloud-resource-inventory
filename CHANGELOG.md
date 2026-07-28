# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.2] - 2026-07-28

### Fixed

- **Azure subscription discovery fails on newer Azure SDK** — Fixed `AttributeError: module 'azure.mgmt.resource' has no attribute 'SubscriptionClient'` when running the Azure collector in environments with `azure-mgmt-resource` 24+ (e.g. Azure Cloud Shell). `SubscriptionClient` was moved to a separate package in Azure SDK v24; subscription discovery now imports from `azure.mgmt.resource.subscriptions`.

### Changed

- Replaced `azure-mgmt-resource` with `azure-mgmt-resource-subscriptions` in Azure optional dependencies (`requirements.txt`, `pyproject.toml`, `setup.py`).
- Updated `check-deps` to validate the new subscriptions package.

### Upgrade notes

**Recommended** — reinstall Azure dependencies:

```bash
pip install --upgrade "lm-cloud-inventory[azure]"
```

**If you cannot upgrade the CLI yet** — temporary workaround (no code change):

```bash
pip install "azure-mgmt-resource>=23.0.0,<24.0.0"
```

Users already on `azure-mgmt-resource` 23.x do not need to change packages; the updated import path remains compatible with that version.

"""Configuration loading utilities."""

import json
import os
from pathlib import Path
from typing import Dict
import logging

logger = logging.getLogger(__name__)


def get_config_path(filename: str) -> Path:
    """
    Get the path to a configuration file.
    
    Searches in order:
    1. Current working directory / config /
    2. Package directory / config /
    3. Repository root / config /
    
    Args:
        filename: Name of the configuration file.
        
    Returns:
        Path to the configuration file.
        
    Raises:
        FileNotFoundError: If the configuration file is not found.
    """
    # Check current working directory
    cwd_config = Path.cwd() / "config" / filename
    if cwd_config.exists():
        return cwd_config

    # Check package directory (relative to this file)
    package_dir = Path(__file__).parent.parent.parent
    package_config = package_dir / "config" / filename
    if package_config.exists():
        return package_config

    # Check environment variable
    env_config_dir = os.environ.get("LM_INVENTORY_CONFIG_DIR")
    if env_config_dir:
        env_config = Path(env_config_dir) / filename
        if env_config.exists():
            return env_config

    raise FileNotFoundError(
        f"Configuration file '{filename}' not found. "
        f"Searched in: {cwd_config}, {package_config}"
    )


def load_resource_mappings(path: str = None) -> Dict:
    """
    Load resource type to category mappings.
    
    Args:
        path: Optional path to the mappings file.
              If not provided, searches default locations.
              
    Returns:
        Dictionary mapping provider -> resource_type -> {category, unit, notes}
        
    Example:
        {
            "aws": {
                "AWS::EC2::Instance": {
                    "category": "IaaS",
                    "unit": "Instance",
                    "notes": "Virtual machines"
                }
            }
        }
    """
    if path:
        config_path = Path(path)
    else:
        config_path = get_config_path("resource_mappings.json")

    logger.info("Loading resource mappings from %s", config_path)

    with open(config_path, 'r', encoding='utf-8') as f:
        mappings = json.load(f)

    return mappings


def load_license_rules(path: str = None) -> Dict:
    """
    Load license calculation rules.
    
    Args:
        path: Optional path to the rules file.
              If not provided, searches default locations.
              
    Returns:
        Dictionary with license calculation rules.
        
    Example:
        {
            "categories": ["IaaS", "PaaS", "Non-Compute"],
            "no_charge_resources": {
                "aws": ["AWS::WAF::*", "AWS::Shield::*"],
                "azure": ["microsoft.advisor/*"]
            }
        }
    """
    if path:
        config_path = Path(path)
    else:
        config_path = get_config_path("license_rules.json")

    logger.info("Loading license rules from %s", config_path)

    with open(config_path, 'r', encoding='utf-8') as f:
        rules = json.load(f)

    return rules

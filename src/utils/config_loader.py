"""Configuration loading utilities."""

import json
import os
from importlib import resources
from pathlib import Path
from typing import Dict
import logging

logger = logging.getLogger(__name__)


def get_config_path(filename: str) -> Path:
    """
    Get the path to a configuration file.
    
    Searches in order:
    1. Environment variable LM_INVENTORY_CONFIG_DIR
    2. Current working directory / config /
    3. Package data (src.config) - for pip installed packages
    
    Args:
        filename: Name of the configuration file.
        
    Returns:
        Path to the configuration file.
        
    Raises:
        FileNotFoundError: If the configuration file is not found.
    """
    searched_paths = []

    # Check environment variable first (allows override)
    env_config_dir = os.environ.get("LM_INVENTORY_CONFIG_DIR")
    if env_config_dir:
        env_config = Path(env_config_dir) / filename
        searched_paths.append(str(env_config))
        if env_config.exists():
            return env_config

    # Check current working directory (for development/custom configs)
    cwd_config = Path.cwd() / "config" / filename
    searched_paths.append(str(cwd_config))
    if cwd_config.exists():
        return cwd_config

    # Use importlib.resources for package data (works with pip install)
    try:
        config_files = resources.files("src.config")
        config_file = config_files.joinpath(filename)
        # Check if the resource exists and is readable
        if config_file.is_file():
            return Path(str(config_file))
    except (ModuleNotFoundError, TypeError, AttributeError):
        pass

    searched_paths.append("src.config (package data)")

    raise FileNotFoundError(
        f"Configuration file '{filename}' not found. "
        f"Searched in: {', '.join(searched_paths)}"
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
                "ec2:instance": {
                    "category": "IaaS",
                    "unit": "Instance"
                }
            }
        }
    """
    if path:
        config_path = Path(path)
        logger.info("Loading resource mappings from %s", config_path)
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    # Try package resources first for pip-installed packages
    try:
        config_files = resources.files("src.config")
        config_file = config_files.joinpath("resource_mappings.json")
        if config_file.is_file():
            logger.debug("Loading resource mappings from package data")
            content = config_file.read_text(encoding='utf-8')
            return json.loads(content)
    except (ModuleNotFoundError, TypeError, AttributeError):
        pass

    # Fallback to file-based loading
    config_path = get_config_path("resource_mappings.json")
    logger.info("Loading resource mappings from %s", config_path)

    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


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
                "aws": ["waf:*", "shield:*"],
                "azure": ["microsoft.advisor/*"]
            }
        }
    """
    if path:
        config_path = Path(path)
        logger.info("Loading license rules from %s", config_path)
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    # Try package resources first for pip-installed packages
    try:
        config_files = resources.files("src.config")
        config_file = config_files.joinpath("license_rules.json")
        if config_file.is_file():
            logger.debug("Loading license rules from package data")
            content = config_file.read_text(encoding='utf-8')
            return json.loads(content)
    except (ModuleNotFoundError, TypeError, AttributeError):
        pass

    # Fallback to file-based loading
    config_path = get_config_path("license_rules.json")
    logger.info("Loading license rules from %s", config_path)

    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

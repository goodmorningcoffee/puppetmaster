"""
pm_config.py - Configuration Management

Handles loading/saving the user configuration file (~/.puppetmaster_config.json).
"""

import json
import sys
from pathlib import Path


# Store in home directory so it survives puppetmaster directory deletions
CONFIG_FILE = Path.home() / ".puppetmaster_config.json"


def load_config():
    """Load saved configuration (output directories, etc.)"""
    try:
        if CONFIG_FILE.exists():
            return json.loads(CONFIG_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        pass
    return {"output_dirs": []}


def save_config(config):
    """Save configuration to disk"""
    try:
        CONFIG_FILE.write_text(json.dumps(config, indent=2))
        return True
    except OSError as e:
        print(f"\n\033[31mWarning: Failed to save config: {e}\033[0m", file=sys.stderr)
        return False


def remember_output_dir(path):
    """Remember an output directory for later retrieval"""
    config = load_config()
    abs_path = str(Path(path).resolve())

    # Add to front of list (most recent first), avoid duplicates
    if abs_path in config["output_dirs"]:
        config["output_dirs"].remove(abs_path)
    config["output_dirs"].insert(0, abs_path)

    # Keep only last 20 directories
    config["output_dirs"] = config["output_dirs"][:20]
    save_config(config)


def get_remembered_output_dirs():
    """Get list of previously used output directories"""
    config = load_config()
    return config.get("output_dirs", [])

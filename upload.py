#!/usr/bin/env python3
"""
Upload Script - Quick recursive upload to remote servers

Purpose:
  Allows you to modify PUPPETMASTER locally and quickly sync changes to a remote
  server (EC2, VPS, etc.). Useful for development workflows where you edit code
  locally but run it on a remote machine.

Features:
  - Remembers your last server, paths, and SSH key
  - Uploads entire directory recursively
  - Automatically makes .py and .sh files executable
  - Falls back to scp if rsync unavailable

Usage:
  python3 upload.py                           # Interactive mode (remembers last settings)
  python3 upload.py ec2-xx-xx-xx.amazonaws.com  # Quick upload to specific server
  python3 upload.py --ip 1.2.3.4              # Use IP address
  python3 upload.py --help                    # Show all options

Configuration:
  Settings are saved in ~/.vuln_upload_config.json (NOT in project directory)
  You'll be prompted for:
    - Remote server address
    - SSH key path (.pem file)
    - Local directory to upload from
    - Remote directory to upload to
"""

import subprocess
import os
import sys
import json
import shlex
import re
from datetime import datetime
from pathlib import Path

# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    # Default SSH key location - UPDATE THIS TO YOUR KEY PATH
    # Common locations: ~/.ssh/id_rsa, ~/Downloads/your-key.pem, ~/keys/server.pem
    DEFAULT_KEY = os.path.expanduser("~/.ssh/id_rsa")

    # Default username (common: ubuntu, ec2-user, kali, root)
    DEFAULT_USER = "kali"

    # Default remote directory
    REMOTE_DIR = "~/puppet"

    # Config file to remember settings (saved in home directory, not project)
    CONFIG_FILE = os.path.expanduser("~/.vuln_upload_config.json")

# ============================================================================
# COLORS
# ============================================================================

class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'

def print_banner():
    print(f"""{Colors.CYAN}{Colors.BOLD}
╔══════════════════════════════════════════════════════════════════════╗
║                        EC2 UPLOADER                                 ║
║              Recursive Upload to Remote Server                      ║
╚══════════════════════════════════════════════════════════════════════╝
{Colors.RESET}""")

def log(level, message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    colors = {
        "INFO": Colors.BLUE,
        "SUCCESS": Colors.GREEN,
        "WARN": Colors.YELLOW,
        "ERROR": Colors.RED,
        "UPLOAD": Colors.PURPLE,
    }
    symbols = {
        "INFO": "ℹ️ ",
        "SUCCESS": "✅",
        "WARN": "⚠️ ",
        "ERROR": "❌",
        "UPLOAD": "📤",
    }
    color = colors.get(level, Colors.RESET)
    symbol = symbols.get(level, "")
    print(f"{color}[{timestamp}] [{level}] {symbol} {message}{Colors.RESET}")

# ============================================================================
# CONFIG MANAGEMENT
# ============================================================================

def sanitize_input(text):
    """Remove terminal escape sequences and control characters from input"""
    # Remove ANSI escape sequences (arrow keys, colors, etc.)
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    text = ansi_escape.sub('', text)
    # Remove other control characters
    text = ''.join(c for c in text if c.isprintable() or c in ' \t')
    return text.strip()


def validate_path(path, must_exist=False, base_dir=None):
    """
    Validate a file path to prevent path traversal attacks.

    Args:
        path: The path to validate
        must_exist: If True, path must exist
        base_dir: If provided, path must be within this directory

    Returns:
        Validated absolute path, or None if invalid
    """
    if not path:
        return None

    # Expand and normalize
    path = os.path.expanduser(path)
    path = os.path.abspath(os.path.normpath(path))

    # Check for path traversal attempts in original input
    if '..' in path or path.startswith('//'):
        return None

    # If base_dir specified, ensure path is within it
    if base_dir:
        base_dir = os.path.abspath(os.path.normpath(os.path.expanduser(base_dir)))
        if not path.startswith(base_dir):
            return None

    # Check existence if required
    if must_exist and not os.path.exists(path):
        return None

    return path


def validate_remote_path(path):
    """
    Validate a remote path for shell safety.

    Returns sanitized path or None if invalid.
    """
    if not path:
        return None

    path = path.strip()

    # Allow ~ expansion but prevent shell injection
    # Only allow alphanumeric, underscore, hyphen, dot, slash, and ~
    if not re.match(r'^[~]?[a-zA-Z0-9_\-./]+$', path):
        return None

    # No double dots (path traversal) - but allow single dots for hidden dirs
    if '..' in path:
        return None

    return path


def load_config():
    """Load saved configuration"""
    if os.path.exists(Config.CONFIG_FILE):
        try:
            with open(Config.CONFIG_FILE) as f:
                config = json.load(f)
                # Sanitize loaded values
                for key in config:
                    if isinstance(config[key], str):
                        config[key] = sanitize_input(config[key])
                return config
        except Exception:
            pass
    return {}

def save_config(config):
    """Save configuration"""
    try:
        with open(Config.CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        log("WARN", f"Could not save config: {e}")

# ============================================================================
# UPLOAD LOGIC
# ============================================================================

def test_connection(host, user, key_path):
    """Test SSH connection to EC2"""
    log("INFO", f"Testing connection to {user}@{host}...")

    cmd = [
        "ssh", "-i", key_path,
        "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=10",
        f"{user}@{host}",
        "echo 'Connection OK'"
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            log("SUCCESS", "Connection successful!")
            return True
        else:
            log("ERROR", f"Connection failed: {result.stderr.strip()}")
            return False
    except subprocess.TimeoutExpired:
        log("ERROR", "Connection timed out")
        return False
    except Exception as e:
        log("ERROR", f"Connection error: {e}")
        return False

def count_items(directory):
    """Count files and directories recursively"""
    files = 0
    dirs = 0
    for root, dirnames, filenames in os.walk(directory):
        # Skip hidden dirs and __pycache__
        dirnames[:] = [d for d in dirnames if not d.startswith('.') and d != '__pycache__']
        files += len([f for f in filenames if not f.startswith('.') and f != '.DS_Store'])
        dirs += len(dirnames)
    return files, dirs


def upload_files(host, user, key_path, local_dir, remote_dir):
    """Upload entire directory recursively using rsync"""

    # Expand path and make absolute
    local_dir = os.path.expanduser(local_dir)
    local_dir = os.path.abspath(local_dir)

    if not os.path.exists(local_dir):
        log("ERROR", f"Local directory not found: {local_dir}")
        return False

    if not os.path.isdir(local_dir):
        log("ERROR", f"Path is not a directory: {local_dir}")
        return False

    # Count items
    file_count, dir_count = count_items(local_dir)
    log("INFO", f"Found {file_count} files in {dir_count + 1} directories")
    log("INFO", f"Uploading to {user}@{host}:{remote_dir}...")

    # Create remote directory
    # Note: StrictHostKeyChecking=no is intentional for EC2 instances which frequently
    # change host keys when instances are replaced. For production systems with stable
    # host keys, consider using StrictHostKeyChecking=accept-new instead.
    safe_remote = shlex.quote(remote_dir) if remote_dir else "'~/puppet'"
    mkdir_cmd = [
        "ssh", "-i", key_path,
        "-o", "StrictHostKeyChecking=no",
        f"{user}@{host}",
        f"mkdir -p {safe_remote}"
    ]
    subprocess.run(mkdir_cmd, capture_output=True)

    # Use rsync for recursive upload (faster, handles directories)
    # Trailing slash on local_dir means "contents of" not "the directory itself"
    log("UPLOAD", "Syncing directory (recursive)...")

    # Build SSH command for rsync - quote paths for safety
    ssh_cmd = f"ssh -i {shlex.quote(key_path)} -o StrictHostKeyChecking=no"

    rsync_cmd = [
        "rsync", "-avz", "--progress",
        "--exclude=__pycache__",
        "--exclude=.DS_Store",
        "--exclude=*.pyc",
        "--exclude=.git",
        "--exclude=.venv",
        "--exclude=venv",
        f"--rsh={ssh_cmd}",
        f"{local_dir}/",  # Trailing slash = contents of directory
        f"{user}@{host}:{remote_dir}/"
    ]

    def scp_contents(local_dir, remote_dest):
        """Upload contents of directory (not the directory itself) using scp"""
        log("UPLOAD", "Uploading directory contents via scp...")
        success = True

        # Items to always skip
        SKIP_ITEMS = {'__pycache__', 'venv', '.venv', '.git', 'node_modules', '.pytest_cache'}

        for item in os.listdir(local_dir):
            # Skip hidden files, junk, and venv directories
            if item.startswith('.') or item in SKIP_ITEMS:
                continue

            item_path = os.path.join(local_dir, item)

            # Get size for timeout calculation (larger files need more time)
            # EXCLUDE venv/node_modules from size calculation
            try:
                if os.path.isdir(item_path):
                    size_mb = sum(
                        os.path.getsize(os.path.join(root, f))
                        for root, dirs, files in os.walk(item_path)
                        if not any(skip in root for skip in SKIP_ITEMS)
                        for f in files
                    ) / (1024 * 1024)
                else:
                    size_mb = os.path.getsize(item_path) / (1024 * 1024)
            except Exception:
                size_mb = 10  # Default

            # Timeout: 120 seconds base + 60 seconds per 10MB (more generous)
            timeout = max(180, int(120 + (size_mb / 10) * 60))

            log("UPLOAD", f"Uploading {item} ({size_mb:.1f} MB, timeout {timeout}s)...")

            # For directories, use tar to properly exclude venv/node_modules
            if os.path.isdir(item_path):
                # Create tar with exclusions, pipe through ssh
                # Use shlex.quote for all user-supplied values to prevent shell injection
                excludes = ' '.join([f"--exclude={shlex.quote(s)}" for s in SKIP_ITEMS])
                tar_cmd = (
                    f"tar -czf - -C {shlex.quote(local_dir)} {excludes} {shlex.quote(item)} | "
                    f"ssh -i {shlex.quote(key_path)} -o StrictHostKeyChecking=no "
                    f"{shlex.quote(user)}@{shlex.quote(host)} "
                    f"'cd {shlex.quote(remote_dest)} && tar -xzf -'"
                )

                try:
                    result = subprocess.run(tar_cmd, shell=True, capture_output=True, text=True, timeout=timeout)
                    if result.returncode == 0:
                        print(f"  {Colors.GREEN}✓{Colors.RESET} {item}")
                    else:
                        error_msg = result.stderr.strip()[:80] if result.stderr else "Unknown error"
                        print(f"  {Colors.RED}✗{Colors.RESET} {item}: {error_msg}")
                        success = False
                except subprocess.TimeoutExpired:
                    print(f"  {Colors.RED}✗{Colors.RESET} {item}: Timeout after {timeout}s")
                    success = False
                except Exception as e:
                    print(f"  {Colors.RED}✗{Colors.RESET} {item}: {e}")
                    success = False
            else:
                # For files, use scp directly
                scp_cmd = [
                    "scp", "-C",  # -C for compression
                    "-i", key_path,
                    "-o", "StrictHostKeyChecking=no",
                    "-o", "ConnectTimeout=30",
                    item_path,
                    f"{user}@{host}:{remote_dest}/"
                ]

                try:
                    result = subprocess.run(scp_cmd, capture_output=True, text=True, timeout=timeout)
                    if result.returncode == 0:
                        print(f"  {Colors.GREEN}✓{Colors.RESET} {item}")
                    else:
                        error_msg = result.stderr.strip()[:80] if result.stderr else "Unknown error"
                        print(f"  {Colors.RED}✗{Colors.RESET} {item}: {error_msg}")
                        success = False
                except subprocess.TimeoutExpired:
                    print(f"  {Colors.RED}✗{Colors.RESET} {item}: Timeout after {timeout}s")
                    success = False
                except Exception as e:
                    print(f"  {Colors.RED}✗{Colors.RESET} {item}: {e}")
                    success = False

        return success

    try:
        # 600 seconds (10 min) timeout for large uploads
        result = subprocess.run(rsync_cmd, capture_output=True, text=True, timeout=600)
        if result.returncode == 0:
            log("SUCCESS", "Upload complete!")
        else:
            error_preview = result.stderr[:200] if result.stderr else "Unknown error"
            log("WARN", f"rsync failed: {error_preview}")
            log("INFO", "Trying scp as fallback...")
            if not scp_contents(local_dir, remote_dir):
                log("ERROR", "Upload failed")
                return False
    except subprocess.TimeoutExpired:
        log("ERROR", "Upload timed out")
        return False
    except FileNotFoundError:
        # rsync not installed, use scp
        log("WARN", "rsync not found, using scp...")
        if not scp_contents(local_dir, remote_dir):
            log("ERROR", "Upload failed")
            return False

    # Make scripts executable (recursively)
    # Note: remote_dir is validated before use, shlex.quote for extra safety
    log("INFO", "Making scripts executable...")
    safe_remote = shlex.quote(remote_dir) if remote_dir else "'~/puppet'"
    chmod_cmd = [
        "ssh", "-i", key_path,
        "-o", "StrictHostKeyChecking=no",
        f"{user}@{host}",
        f"find {safe_remote} -name '*.py' -o -name '*.sh' | xargs chmod +x 2>/dev/null || true"
    ]
    subprocess.run(chmod_cmd, capture_output=True)

    log("SUCCESS", f"Uploaded {file_count} files in {dir_count + 1} directories")
    return True

def get_ec2_address():
    """Get EC2 address from user or saved config"""
    config = load_config()
    last_host = config.get('last_host', '')

    if last_host:
        print(f"\n{Colors.CYAN}Last used EC2:{Colors.RESET} {last_host}")
        print(f"{Colors.DIM}Press Enter to use, 'n' for new, or paste new address directly{Colors.RESET}")
        response = sanitize_input(input(f"Use this? [Y/n/new-address]: "))

        # Empty = use last
        if not response or response.lower() == 'y':
            return last_host

        # 'n' = prompt for new
        if response.lower() == 'n':
            pass  # Fall through to prompt below
        # Anything else that looks like an address = use it directly
        elif '.' in response or 'ec2' in response.lower():
            config['last_host'] = response
            save_config(config)
            return response

    print(f"\n{Colors.CYAN}Enter EC2 address:{Colors.RESET}")
    print(f"  Examples: ec2-54-211-76-29.compute-1.amazonaws.com")
    print(f"            54.211.76.29")

    host = sanitize_input(input(f"\n{Colors.BOLD}EC2 address: {Colors.RESET}"))

    if not host:
        log("ERROR", "No address provided")
        return None

    # Save for next time
    config['last_host'] = host
    save_config(config)

    return host

def get_local_directory():
    """Get local directory to upload from user or saved config"""
    config = load_config()

    # Default to vuln_code if it exists in current directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_dir = os.path.join(script_dir, 'vuln_code')

    # Check saved config
    last_dir = config.get('local_dir', default_dir if os.path.exists(default_dir) else script_dir)

    print(f"\n{Colors.CYAN}Local directory to upload:{Colors.RESET}")
    print(f"  Last used: {last_dir}")

    # Check if it exists and show contents
    if os.path.exists(last_dir) and os.path.isdir(last_dir):
        file_count = len([f for f in os.listdir(last_dir) if os.path.isfile(os.path.join(last_dir, f))])
        print(f"  Files: {file_count}")

    new_dir = sanitize_input(input(f"\nPath [{last_dir}]: "))

    if new_dir:
        local_dir = new_dir
    else:
        local_dir = last_dir

    # Expand and validate
    local_dir = os.path.expanduser(local_dir)
    local_dir = os.path.abspath(local_dir)

    if not os.path.exists(local_dir):
        log("ERROR", f"Directory not found: {local_dir}")
        return None

    if not os.path.isdir(local_dir):
        log("ERROR", f"Path is not a directory: {local_dir}")
        return None

    # Save for next time
    config['local_dir'] = local_dir
    save_config(config)

    return local_dir

def get_remote_dir():
    """Get remote directory from user or saved config"""
    config = load_config()
    last_dir = config.get('remote_dir') or '~/puppet'  # Default to ~/puppet if empty

    # Ensure we have a valid remote dir
    if not last_dir or last_dir.isspace():
        last_dir = '~/puppet'

    # Validate saved path
    if not validate_remote_path(last_dir):
        last_dir = '~/puppet'

    print(f"\n{Colors.CYAN}Remote directory:{Colors.RESET} {last_dir}")
    new_dir = sanitize_input(input(f"Change? (Enter to keep, or type new path): "))

    if new_dir:
        # Validate new path for shell safety
        validated = validate_remote_path(new_dir)
        if not validated:
            log("WARN", "Invalid path format. Using default ~/puppet")
            remote_dir = '~/puppet'
        else:
            remote_dir = validated
    else:
        remote_dir = last_dir

    # Save for next time
    config['remote_dir'] = remote_dir
    save_config(config)

    return remote_dir

def get_key_path():
    """Get SSH key path"""
    config = load_config()

    # Check if default key exists
    if os.path.exists(Config.DEFAULT_KEY):
        return Config.DEFAULT_KEY

    # Check saved key
    saved_key = config.get('key_path')
    if saved_key and os.path.exists(saved_key):
        return saved_key

    # Ask user
    print(f"\n{Colors.YELLOW}SSH key not found at default location:{Colors.RESET}")
    print(f"  {Config.DEFAULT_KEY}")

    key_path = sanitize_input(input(f"\n{Colors.BOLD}Enter path to your .pem key: {Colors.RESET}"))
    key_path = os.path.expanduser(key_path)

    if not os.path.exists(key_path):
        log("ERROR", f"Key not found: {key_path}")
        return None

    # Save for next time
    config['key_path'] = key_path
    save_config(config)

    return key_path

# ============================================================================
# MAIN
# ============================================================================

def main():
    print_banner()

    # Parse command line arguments
    host = None
    key_path = None
    remote_dir = None

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ['--ip', '--host'] and i + 1 < len(args):
            host = args[i + 1]
            i += 2
        elif arg in ['--key', '-k'] and i + 1 < len(args):
            key_path = args[i + 1]
            i += 2
        elif arg in ['--dir', '-d'] and i + 1 < len(args):
            remote_dir = args[i + 1]
            i += 2
        elif arg in ['--help', '-h']:
            print(f"""
{Colors.BOLD}Usage:{Colors.RESET}
  python3 upload.py                              # Interactive mode
  python3 upload.py <ec2-address>                # Quick upload
  python3 upload.py --ip 1.2.3.4                 # Use IP address
  python3 upload.py --dir ~/mydir               # Specify remote directory
  python3 upload.py --key /path/to/key.pem      # Specify SSH key

{Colors.BOLD}Examples:{Colors.RESET}
  python3 upload.py ec2-54-211-76-29.compute-1.amazonaws.com
  python3 upload.py 54.211.76.29 --dir ~/security_tools
  python3 upload.py --ip 54.211.76.29 --key ~/mykey.pem

{Colors.BOLD}Configuration:{Colors.RESET}
  Default key: {Config.DEFAULT_KEY}
  Config file: {Config.CONFIG_FILE}
  (Remembers your last EC2, local directory, remote directory, and key path)

{Colors.BOLD}What it does:{Colors.RESET}
  - Asks for local directory to upload from (default: vuln_code/)
  - Uploads ALL files from that directory to EC2
  - Automatically makes .py and .sh files executable
""")
            sys.exit(0)
        elif not arg.startswith('-'):
            host = arg
            i += 1
        else:
            i += 1

    # Get EC2 address
    if not host:
        host = get_ec2_address()
        if not host:
            sys.exit(1)

    # Get local directory
    local_dir = get_local_directory()
    if not local_dir:
        sys.exit(1)

    # Get remote directory
    if not remote_dir:
        remote_dir = get_remote_dir()

    # Get SSH key
    if not key_path:
        key_path = get_key_path()
        if not key_path:
            sys.exit(1)

    print(f"\n{Colors.BOLD}Upload Configuration:{Colors.RESET}")
    print(f"  Local:  {local_dir}")
    print(f"  EC2:    {host}")
    print(f"  User:   {Config.DEFAULT_USER}")
    print(f"  Key:    {key_path}")
    print(f"  Remote: {remote_dir}")

    # Test connection
    print()
    if not test_connection(host, Config.DEFAULT_USER, key_path):
        print(f"\n{Colors.RED}Connection failed. Check:{Colors.RESET}")
        print("  1. EC2 instance is running")
        print("  2. Security group allows SSH (port 22)")
        print("  3. Correct key file")
        sys.exit(1)

    # Upload files
    print()
    success = upload_files(host, Config.DEFAULT_USER, key_path, local_dir, remote_dir)

    # Summary
    print(f"\n{Colors.GREEN}{'='*60}")
    print(f"  UPLOAD COMPLETE!")
    print(f"{'='*60}{Colors.RESET}")

    print(f"\n{Colors.BOLD}To connect to EC2:{Colors.RESET}")
    print(f"  ssh -i {key_path} {Config.DEFAULT_USER}@{host}")
    print(f"  cd {remote_dir}")

    # Save successful host
    config = load_config()
    config['last_host'] = host
    config['key_path'] = key_path
    save_config(config)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Cancelled{Colors.RESET}")
        sys.exit(0)

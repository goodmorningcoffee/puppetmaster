# PUPPETMASTER

## SpiderFoot Sock Puppet Detector

> *"Finding the strings that connect the puppets"*

```
╭─────────────────────────────────────────────────────────────────────────────────────────────╮
│ MISSION STATUS  Q:357 ██████  S:24 ████░░  C:3 ██░░░░  BL:231  [SCANNING]                   │
╰─────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ LOADOUT ────────────────────────────────╮  ╭─ ACTIVE MISSION ──────────────────────────────╮
│                                          │  │                                               │
│  DISCOVERY & SCANNING                    │  │  [5] PUPPET ANALYSIS                          │
│  ────────────────────                    │  │  Detect Sock Puppet Networks                  │
│   [1] Scrape domains (keywords)          │  │                                               │
│   [2] Load domains (file)                │  │  Analyze SpiderFoot exports to detect         │
│  >[3] SpiderFoot Control Center          │  │  domains sharing infrastructure signals       │
│   [4] Check scan queue                   │  │  that prove common ownership.                 │
│                                          │  │                                               │
│  ANALYSIS                                │  │  - Graph-based network analysis               │
│  ────────                                │  │  - Community detection clustering             │
│   [5] Puppet Analysis                    │  │  - Executive summary reports                  │
│   [6] View results                       │  ╰───────────────────────────────────────────────╯
│   [11] Wildcard DNS filter               │  ╭─ SYSTEM VITALS ───────────────────────────────╮
│                                          │  │  CPU  [████░░░░░░░░░░░░]  23%                 │
│  SETTINGS                                │  │  MEM  [██████░░░░░░░░░░]  41%                 │
│  ────────                                │  │  DISK [████████░░░░░░░░]  54%                 │
│   [7] Configuration                      │  ╰───────────────────────────────────────────────╯
│   [8] Help & Documentation               │  ╭─ SCAN QUEUE ──────────────────────────────────╮
│   [9] Launch in tmux                     │  │  357 domains ready                            │
│   [10] System monitor                    │  │  Scanning: competitor-site.com                │
│                                          │  │  Progress: 24/357 (7%)                        │
│  SECURITY                                │  ╰───────────────────────────────────────────────╯
│  ────────                                │  ╭───────────────────────────────────────────────╮
│   [S] Security Audit                     │  │  ██████╗ ██╗   ██╗██████╗ ██████╗ ███████╗    │
│                                          │  │  ██╔══██╗██║   ██║██╔══██╗██╔══██╗██╔════╝    │
│  KALI ENHANCED (if on Kali)              │  │  ██████╔╝██║   ██║██████╔╝██████╔╝█████╗      │
│  ──────────────────────                  │  │  ██╔═══╝ ██║   ██║██╔═══╝ ██╔═══╝ ██╔══╝      │
│   [K1]-[K5] OSINT Tools                  │  │  ██║     ╚██████╔╝██║     ██║     ███████╗    │
│                                          │  │  ╚═╝      ╚═════╝ ╚═╝     ╚═╝     ╚══════╝    │
╰──────────────────────────────────────────╯  ╰───────────────────────────────────────────────╯
╭─────────────────────────────────────────────────────────────────────────────────────────────╮
│ DEPLOY [ENTER]    SELECT [UP/DOWN]    DIRECT [1-11]    EXIT [Q]                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────╯
```

PUPPETMASTER is an end-to-end pipeline for detecting coordinated networks of domains ("sock puppets") that are secretly controlled by the same entity. It combines domain discovery, [SpiderFoot](https://github.com/smicallef/spiderfoot) OSINT scanning, and graph-based network analysis.

---

## What Does This Tool Do?

### The Complete Pipeline

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  DISCOVER   │ ──▶ │    SCAN     │ ──▶ │   ANALYZE   │
│  Domains    │     │  SpiderFoot │     │   Network   │
└─────────────┘     └─────────────┘     └─────────────┘
```

1. **Discover** - Scrape Google/DuckDuckGo for competitor or suspicious domains using keywords
2. **Scan** - Run SpiderFoot OSINT scans in batch mode or interactive Web GUI
3. **Analyze** - Detect shared infrastructure that proves common ownership

### What We Find

| Signal Type | Example | Meaning |
|-------------|---------|---------|
| Same Google Analytics ID | UA-12345678-1 | **Definitive proof** of same operator |
| Same AdSense Publisher ID | pub-1234567890 | **Definitive proof** of same operator |
| Same Google Site Verification | Token string | **Definitive proof** of same operator |
| Same WHOIS registrant | John Doe, 123 Main St | Strong evidence |
| Same nameservers | ns1.customdns.com | Strong evidence |
| Same SSL certificate | SHA256 fingerprint | **Definitive proof** |

**One shared unique identifier = same operator.**

### Use Cases

- Detecting fake review networks
- Identifying coordinated disinformation campaigns
- Competitor intelligence
- Fraud investigation
- Any situation where you suspect multiple websites are secretly controlled by one entity

---

## Quick Start

### Prerequisites

- Python 3.9 or higher (uses modern type hints)
- SpiderFoot (auto-installed if not present)
- 4GB+ RAM recommended for large datasets

### Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/puppetmaster.git
cd puppetmaster

# Run PUPPETMASTER (auto-creates venv and installs dependencies)
python3 puppetmaster.py
```

That's it! PuppetMaster automatically handles virtual environment creation and dependency installation.

> **Security Note**: Dependencies are installed with hash verification to protect against supply chain attacks. See [SECURITY.md](SECURITY.md) for more details.

### Platform-Specific Notes

**Kali Linux (Recommended):**
```bash
# Ensure venv support is installed
sudo apt update && sudo apt install python3-venv

# Run PuppetMaster (handles venv automatically)
python3 puppetmaster.py
```
Kali automatically detects and enables additional OSINT tools (theHarvester, Amass, DNSRecon, etc.)

**Ubuntu/Debian:**
```bash
sudo apt update && sudo apt install python3 python3-pip python3-venv
```

**macOS:**
```bash
# Via Homebrew:
brew install python3
```

**Windows:**
- Download Python from [python.org](https://python.org)
- Check "Add Python to PATH" during installation
- Run from Command Prompt or PowerShell

**AWS EC2 / Cloud Servers:**
- Works great on t3.micro or larger
- Use Option [9] (tmux) to keep scans running after SSH disconnect
- Use **[3] SpiderFoot Control Center** → **Open Web GUI** with SSH tunnel for interactive access

---

## SSH Agent Setup (Required for Distributed Scanning)

If you're using EC2 workers for distributed scanning, you **must** use SSH agent forwarding. This keeps your .pem key on your local machine only - never upload it to EC2.

### Step-by-Step: Connecting to EC2 with Agent Forwarding

**Do this on your local Mac/Linux terminal every time you connect:**

**Step 1:** Start the SSH agent (only needed once per terminal session)
```bash
eval "$(ssh-agent -s)"
```
You should see output like: `Agent pid 12345`

**Step 2:** Add your .pem key to the agent (use the actual path to YOUR key)
```bash
# Example if your key is in Downloads:
ssh-add ~/Downloads/my-aws-key.pem

# Example if your key is in .ssh:
ssh-add ~/.ssh/my-aws-key.pem

# Example with full path:
ssh-add /Users/yourname/Documents/keys/my-aws-key.pem
```
You should see: `Identity added: ...`

**Step 3:** Connect to EC2 with the `-A` flag (this forwards your agent)
```bash
ssh -A ubuntu@ec2-12-34-56-78.compute-1.amazonaws.com
```
Replace `ubuntu` with your EC2 username (could be `kali`, `ec2-user`, etc.) and use your actual EC2 hostname.

**Step 4:** Verify the agent is forwarded (run this ON the EC2 instance after connecting)
```bash
ssh-add -l
```
You should see your key fingerprint. If you see "Could not open connection to authentication agent", go back to Step 1.

### Why This Matters

| Without Agent Forwarding | With Agent Forwarding |
|-------------------------|----------------------|
| .pem file copied to EC2 | .pem stays on your laptop |
| If EC2 hacked, key is stolen | If EC2 hacked, key is safe |
| Attacker can spin up instances | Attacker has no key access |

> **Security Note**: A previous attack on this project succeeded because a .pem file was uploaded to an EC2 instance. The attacker used it to spin up crypto mining instances. Use agent forwarding instead.

### macOS: Persist Keys Across Terminals (Recommended)

By default, each terminal window has its own ssh-agent. To share your key across all terminals, use macOS Keychain:

**One-time setup** - add to `~/.ssh/config`:
```
Host *
    AddKeysToAgent yes
    UseKeychain yes
    IdentityFile ~/Downloads/your-key.pem
```

**Then add your key to Keychain:**
```bash
ssh-add --apple-use-keychain ~/Downloads/your-key.pem
```

Now any new terminal will automatically have access to your key without running `ssh-add` each time.

### Troubleshooting: Kali Linux AMI (2025.4+)

**Problem:** Starting with Kali 2025.4, the AMI ships with a systemd `ssh-agent.socket` that overrides SSH agent forwarding. Symptoms include:
- `ssh-add -l` on EC2 shows "no identities" even when using `-A` flag
- `SSH_AUTH_SOCK` points to `/home/kali/.ssh/agent/...` instead of `/tmp/ssh-...`
- Master can't connect to workers despite correct security group rules

**Fix:** Run this on **each EC2 instance** (master and all workers):

```bash
# Disable the systemd ssh-agent socket
sudo systemctl --global disable ssh-agent.socket

# Reboot for changes to take effect
sudo reboot
```

After reboot, reconnect with `-A` and verify:
```bash
# On your local machine:
ssh -A -i /path/to/key.pem kali@your-ec2-host

# On EC2 (should show your key):
ssh-add -l

# SSH_AUTH_SOCK should now look like /tmp/ssh-XXXXX/agent.XXXXX
echo $SSH_AUTH_SOCK
```

### Troubleshooting: General SSH Agent Issues

**"The agent has no identities" on EC2:**

1. **Check your local agent first** (on your Mac/Linux):
   ```bash
   ssh-add -l
   ```
   If this shows nothing, add your key:
   ```bash
   ssh-add /path/to/your-key.pem
   ```

2. **Use the same terminal** - If you ran `ssh-add` in one terminal but SSH'd from a different terminal, the agent won't be shared (unless you configured Keychain as shown above).

3. **Verify you used `-A` flag** when connecting:
   ```bash
   ssh -A -i /path/to/key.pem user@host
   ```

**Connections were working, now they fail:**

Stale puppetmaster processes can cause connection issues. On your master EC2:
```bash
# Kill any running puppetmaster processes
pkill -9 -f puppetmaster.py

# Remove stale state (if needed)
rm -rf ~/puppet

# Restart puppetmaster fresh
cd ~/puppetmaster && python3 puppetmaster.py
```

**Quick diagnostic commands:**

```bash
# On local machine - verify key is loaded:
ssh-add -l

# On EC2 - check what SSH_AUTH_SOCK is set to:
echo $SSH_AUTH_SOCK

# On EC2 - verify agent forwarding worked:
ssh-add -l

# Test worker connectivity from master:
ssh kali@worker-hostname 'echo works'
```

---

## EC2 Setup for Distributed Scanning

Before using the distributed C2 features, you need to set up your EC2 instances correctly.

### Instance Requirements

| Role | Recommended | Minimum |
|------|-------------|---------|
| Master | t3.small | t3.micro |
| Workers | t3.medium (5+ recommended) | t3.small |

All instances should use **Kali Linux AMI** or **Ubuntu 22.04+**.

### Security Group Configuration

Your master needs to SSH into workers. You must configure Security Groups to allow this.

**Step 1:** Get your master's private IP (run this on the master):
```bash
hostname -I | awk '{print $1}'
```
Example output: `172.31.45.123`

**Step 2:** In AWS Console, go to **EC2 → Security Groups**

**Step 3:** Find the Security Group attached to your worker instances

**Step 4:** Edit **Inbound Rules** and add:

| Type | Port | Source | Description |
|------|------|--------|-------------|
| SSH | 22 | 172.31.45.123/32 | Master private IP |

Replace `172.31.45.123` with your actual master private IP.

> **Tip:** If all your workers share the same Security Group, you only need to add this rule once.

### Alternative: Allow Entire VPC (less restrictive)

If you don't want to update rules when master IP changes:

| Type | Port | Source | Description |
|------|------|--------|-------------|
| SSH | 22 | 172.31.0.0/16 | All VPC traffic |

Check your VPC CIDR in **VPC → Your VPCs** (usually `172.31.0.0/16` or `10.0.0.0/16`).

### Verify Connectivity

From your master, test SSH to a worker:
```bash
ssh ubuntu@<worker-private-ip>
```

If it connects, your Security Group is configured correctly.

---

## Distributed Scanning (Multi-EC2)

For large-scale scanning (100-500+ domains), PUPPETMASTER includes a **distributed C2 controller** that coordinates scans across multiple EC2 workers:

```
┌─────────────┐
│   MASTER    │ ──▶ Coordinates 5+ EC2 workers
│  (your PC)  │     Automatic work distribution
└─────────────┘     Real-time progress monitoring
      │
      ├──▶ Worker 1 (EC2) - Scanning domains 1-75
      ├──▶ Worker 2 (EC2) - Scanning domains 76-150
      ├──▶ Worker 3 (EC2) - Scanning domains 151-225
      ├──▶ Worker 4 (EC2) - Scanning domains 226-300
      └──▶ Worker 5 (EC2) - Scanning domains 301-371
```

**Access:** SpiderFoot Control Center → [D] Multi-EC2 C2 Controller

### C2 Submenu

```
WORKER MANAGEMENT
[1] View Worker Status          [5] Setup Workers (install SF)
[2] Add Worker                  [6] EC2 Setup & Cost Guide
[3] Remove Worker               [7] Replace Worker Addresses
[4] Configure SSH Key

SCAN OPERATIONS
[S] Start Distributed Scan      [V] View Aborted Domains
[P] Check Progress              [C] Collect Results
[A] Stop All Scans              [G] GUI Access (SSH tunnels)
[B] Abort All Scans             [D] Debug Worker Logs

DATABASE MANAGEMENT
[R] Reset Worker Databases      [W] Verify Workers Clean

SECURITY                        SETTINGS
[X] Security Audit              [M] Scan Mode (WebAPI/CLI)
                                [T] Scan Settings (parallelism, timeouts)
```

### WebAPI vs CLI Mode

| | **WebAPI** (recommended) | **CLI** |
|--|--------------------------|---------|
| How it works | SpiderFoot web server + REST API | `sf.py -s domain -o csv` per scan |
| Parallelism | Up to **50** scans per worker | Up to **10** scans per worker |
| Queue model | Rolling — submits as slots open | Serial bash scripts |

WebAPI mode is the default and recommended. Toggle with C2 menu → **[M] Scan Mode**.

### Scan Settings

Configurable via C2 menu → **[T] Scan Settings**:
- **Parallel scans per worker** — auto-detected from worker RAM, or set manually
- **Hard timeout** — max hours per scan (default: 6h)
- **Activity timeout** — kill scan if no output for N minutes (default: 60min)
- **AWS region** — configurable (no longer hardcoded to us-east-1)

### Operational Notes

> **Starting fresh?** Always run: **Reset Worker Databases → Setup Workers → Verify Workers Clean** before launching scans. This ensures no stale scan data interferes with new sessions.

**Understanding Process Counts:**

When you set "5 concurrent scans" per worker, you'll see MORE than 5 Python processes on each worker. This is normal - SpiderFoot uses internal multiprocessing:

- **5 sf.py processes** = Your 5 concurrent scans
- **Additional Python processes** = SpiderFoot's internal workers (module execution, threading)

**Rolling Queue Behavior:**

The master machine manages a rolling queue for each worker:
1. Submits up to N scans initially (where N = concurrent limit)
2. Polls each worker to check running scan count
3. Submits more scans as slots become available
4. **Important:** The master must stay running to manage the queue

If connection to a worker is lost, the queue pauses for that worker (fails safe - won't flood).

---

## Step-by-Step Guide

### Option A: Full Pipeline (Discovery → Scan → Analyze)

1. **Start PUPPETMASTER:** `python3 puppetmaster.py`
2. **[1] Scrape domains** - Enter keywords like "competitor keyword site" to find domains
3. **[3] SpiderFoot Control Center** → Start Batch Scans - Scans all discovered domains
4. **[5] Run Puppet Analysis** - Detects connections and generates reports

### Option B: Analyze Existing SpiderFoot Data

If you already have SpiderFoot CSV exports:

1. **Start PUPPETMASTER:** `python3 puppetmaster.py`
2. **[5] Run Puppet Analysis** - Point to your folder of CSV exports
3. **Review reports** in the output directory

### Option C: Interactive GUI Mode

For exploring SpiderFoot's full capabilities:

1. **[3] SpiderFoot Control Center** → **Open Web GUI** - Launches SpiderFoot's web interface
2. **Open browser** to http://localhost:5001 (or use SSH tunnel for remote)
3. **Create scans manually**, export results when done
4. **[5] Run Analysis** on exported CSVs

---

## Remote Access (SSH Tunnels)

Running on a remote server (EC2, VPS)?

### For SpiderFoot Web GUI:

```bash
# On your local machine, create SSH tunnel:
ssh -L 5001:localhost:5001 user@your-server

# Then open in your local browser:
http://localhost:5001
```

### For Long-Running Scans:

Use **Option [9]** to launch in tmux. Your scan keeps running even if SSH disconnects:

```bash
# Detach from session:
Ctrl+b, then d

# Later, reattach:
tmux attach -t puppetmaster
```

---

## Wildcard DNS Filtering

Menu option **[11] Signal//Noise Wildcard DNS Analyzer** filters out domains using wildcard/catch-all DNS — where any subdomain resolves to the same IP. These are typically parked domains, domain squatters, or hosting providers with catch-all DNS records.

Filtering these before analysis reduces false positives, since infrastructure-sharing signals from wildcard DNS domains are meaningless.

**Standalone mode** for batch DNS analysis:
```bash
python3 wildcardDNS_analyzer.py --domain example.com
```

---

## Infrastructure Analysis

Standalone cross-domain infrastructure correlation tool, separate from the Kali integration (works on any platform):

```bash
python3 infra_analysis.py
```

Analyzes domains for shared infrastructure: IP addresses, SSL certificates, nameservers, and technology stacks. Use as a supplementary detection method alongside the main puppet analysis pipeline.

---

## Understanding the Results

### Output Files

| File | Description |
|------|-------------|
| `executive_summary.md` | **Start here!** Human-readable overview |
| `smoking_guns.csv` | All definitive connections with evidence |
| `clusters.csv` | Domain cluster assignments |
| `hub_analysis.csv` | Potential controller/C2 domains |
| `all_connections.csv` | Complete connection list |
| `signals.csv` | All extracted signals |
| `network.graphml` | Graph file for visualization tools |

### Signal Classification

| Tier | Meaning | Examples |
|------|---------|----------|
| SMOKING_GUN | One match = definitive connection | Same Google Analytics ID, Same email, Same SSL cert |
| STRONG | 2+ matches = likely connected | Same WHOIS registrant, Same phone number |
| NOISE | Ignored (too common) | Same CDN, Same cloud hosting provider |

### Confidence Levels

- **CONFIRMED** - At least one smoking gun signal
- **LIKELY** - Multiple strong signals
- **POSSIBLE** - Some strong signals
- **WEAK** - Only weak/supporting signals

---

## Security Audit

PUPPETMASTER includes a built-in security audit module (**[S]** from main menu) for detecting rootkits and system compromises:

| Tool | Purpose |
|------|---------|
| chkrootkit | Rootkit signature detection |
| rkhunter | Rootkit hunter + backdoor detection |
| lynis | Full security audit |
| debsums | Package integrity verification |
| unhide | Hidden process/port detection |

**Features:**
- Audit local machine or all distributed workers
- Auto-install missing tools
- Clear disclaimer about what it can/cannot detect

> **Important**: These tools detect known rootkits and backdoors, but **cannot** detect supply chain attacks or credential theft. See the disclaimer in the Security Audit menu for full details.

---

## Kali Linux Integration

When running on Kali Linux, PUPPETMASTER automatically detects and integrates with additional OSINT tools:

| Tool | Purpose |
|------|---------|
| theHarvester | Email and subdomain enumeration |
| Amass | Advanced DNS enumeration |
| DNSRecon | DNS record analysis |
| DNSEnum | DNS zone enumeration |
| Sublist3r | Subdomain discovery |
| Fierce | DNS reconnaissance |
| WhatWeb | Web technology fingerprinting |
| wafw00f | WAF detection |
| SSLScan | SSL/TLS analysis |
| Nmap | Port and service scanning |
| Nikto | Web vulnerability scanning |
| Metagoofil | Document metadata extraction |
| ExifTool | File metadata analysis |
| DMitry | Deepmagic Information Tool |
| Sherlock | Social media username search |

### Scan Modes [K2]

| Mode | Description | Detection Risk |
|------|-------------|----------------|
| **GHOST** | Passive only — zero target contact | None |
| **STEALTH** | Light touch — 1-2 requests per domain | Low |
| **STANDARD** | Balanced reconnaissance (default) | Medium |
| **DEEP** | Maximum coverage — all tools enabled | High |

### Infrastructure Correlation [K5]

Cross-references results from all Kali tools to find connections between domains: shared IPs, shared SSL certificates, shared nameservers, shared email addresses, same document authors, and matching social media usernames. Each signal type is weighted by reliability (e.g., shared SSL fingerprint = 1.0, shared IP = 0.9, shared tech stack = 0.5).

---

## Dependencies

Core dependencies are auto-installed on first run:

```
pandas          # Data manipulation
networkx        # Graph analysis
tqdm            # Progress bars
tldextract      # Domain parsing
matplotlib      # Visualization
python-louvain  # Community detection (REQUIRED for accurate clustering)
googlesearch-python  # Google search
ddgs            # DuckDuckGo search
rich            # Terminal UI
psutil          # System monitoring
dnspython       # DNS resolution
simple-term-menu  # Domain review UI
```

---

## FAQ

### How accurate is this?

**Smoking guns are extremely reliable.** If two domains share the same Google Analytics ID, they're definitively controlled by the same entity.

Strong signals are probabilistic. Two matching signals = high confidence.

### What if I get no results?

Could mean:
1. The domains aren't actually connected
2. The operators use different tracking/analytics per domain
3. SpiderFoot didn't capture the relevant data
4. Privacy protections hide connecting signals (WHOIS privacy, etc.)

### How many domains can I analyze?

Single-machine: tested with 100+ domains / 13 million SpiderFoot rows. For 500+ domains, use the distributed C2 controller to scan across multiple EC2 workers in parallel.

### What's WebAPI mode?

WebAPI mode uses SpiderFoot's web server and REST API for scan submission, enabling up to 50 parallel scans per worker (vs 10 in CLI mode). It's the default and recommended mode. Toggle in C2 menu → [M] Scan Mode.

### Can I use this without SpiderFoot?

Currently no. PUPPETMASTER is designed for SpiderFoot data. The tool can auto-install SpiderFoot for you.

---

## Advanced Usage

### Programmatic Access

```python
from core.pipeline import run_full_pipeline

success = run_full_pipeline(
    input_dir="/path/to/spiderfoot/exports",
    output_dir="/path/to/results"
)
```

### Custom Signal Patterns

Edit `core/signals.py` to add custom signal patterns:

```python
SIGNAL_CONFIG = {
    'my_custom_signal': {
        'tier': SignalTier.SMOKING_GUN,
        'patterns': [r'my-pattern-\d+'],
        'spiderfoot_types': ['My Data Type'],
    },
}
```

---

## License

MIT License - Use freely, attribution appreciated.

---

## Credits

- Built with [Claude](https://claude.ai)
- Powered by [SpiderFoot](https://github.com/smicallef/spiderfoot)
- Network analysis via [NetworkX](https://networkx.org/)
- Community detection via [python-louvain](https://github.com/taynaud/python-louvain)

---

## Development

### upload.py — EC2 Deployment Helper

`upload.py` is a deployment helper for pushing your local codebase to a remote EC2 master instance. It recursively syncs files while excluding sensitive data and unnecessary directories.

```bash
python3 upload.py
```

### Modifying Puppetmaster and Testing on EC2

If you're developing locally and using `upload.py` to push changes to your master EC2 instance, you **must kill all running processes** before re-uploading. Otherwise the old code continues running in memory.

**On your master EC2, before re-uploading:**

```bash
# Kill puppetmaster and its tmux session
tmux kill-session -t puppetmaster 2>/dev/null; pkill -f puppetmaster.py

# Then remove the old directory
sudo rm -rf ~/puppetmaster
```

**Or as a one-liner:**
```bash
tmux kill-session -t puppetmaster 2>/dev/null; pkill -f puppetmaster.py; sudo rm -rf ~/puppetmaster
```

**Then from your local machine:**
```bash
python upload.py
```

**Why this matters:**
- Python processes keep running with old code in memory
- File handles may stay open
- Your changes won't take effect until the old process dies
- You'll get confusing bugs where behavior doesn't match your code

**Tip:** You can check if puppetmaster is still running with:
```bash
ps aux | grep puppetmaster
# or use htop/glances
```

---

## Troubleshooting

### Common Issues

**"ModuleNotFoundError: No module named 'community'"**
```bash
pip install python-louvain
```
Note: The package is `python-louvain` on PyPI but imports as `community`.

**SpiderFoot not finding data**
- Ensure SpiderFoot scans have completed
- Check that CSV exports contain the expected columns
- Try running SpiderFoot manually to verify it's working

**Memory errors with large datasets**
- PUPPETMASTER loads CSV data into memory
- For very large datasets (1M+ rows), consider:
  - Running on a machine with more RAM
  - Processing in batches
  - Using the distributed scanning feature

**SSH connection issues (C2 mode)**
- Verify your PEM key has correct permissions: `chmod 400 key.pem`
- Ensure EC2 security groups allow SSH (port 22)
- Check that the username matches your EC2 AMI (ubuntu, ec2-user, etc.)

**Scans hanging or timing out**
- Some domains may block SpiderFoot
- Use the [V] View Aborted Domains feature to identify problematic domains
- Adjust timeouts in Scan Settings [T]

---

## Issues & Contributing

Found a bug? Have an idea? Open an issue on GitHub.

Pull requests welcome!

---

*PUPPETMASTER - Because sock puppets should be on children's shows, not the internet.*

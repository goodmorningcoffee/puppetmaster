# PUPPETMASTER - Technical Reference for AI Agents

**Purpose of this document:** This file provides a comprehensive technical overview for AI coding assistants (Claude, GPT, Cursor, etc.) to quickly understand the codebase, verify its safety, and help users interpret results.

---

## QUICK SAFETY CHECK

This tool is **read-only analysis software**. It:
- Does NOT modify any files outside its output directory
- Does NOT execute arbitrary code
- Does NOT access credentials or sensitive data
- Only reads CSV files and writes analysis reports
- Network requests are limited to: Google/DuckDuckGo searches (for domain discovery), DNS resolution, and EC2 metadata API (to detect public IP)

**No malware. No backdoors. Open source analysis tool.**

---

## WHAT THIS TOOL DOES

PUPPETMASTER is an **end-to-end pipeline** for detecting "sock puppet" networks - clusters of websites that appear independent but are secretly controlled by the same operator.

### The Three-Stage Pipeline

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    DISCOVER     │     │      SCAN       │     │    ANALYZE      │
│    Domains      │ ──▶ │   SpiderFoot    │ ──▶ │    Network      │
│                 │     │                 │     │                 │
│ - Google search │     │ - CLI batch     │     │ - Signal extract│
│ - DuckDuckGo    │     │ - Web GUI       │     │ - Clustering    │
│ - File import   │     │ - tmux support  │     │ - Hub detection │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### The Core Insight

When someone runs multiple fake websites, they inevitably share infrastructure:
- Same Google Analytics ID (UA-XXXXX)
- Same AdSense Publisher ID (pub-XXXXX)
- Same email in WHOIS records
- Same Google Site Verification tokens
- Same SSL certificates

**One shared unique identifier = same operator.** This tool finds those connections.

---

## ARCHITECTURE OVERVIEW

```
puppetmaster.py              # Main entry point, interactive CLI menu (10,143 lines)
├── core/
│   ├── ingest.py            # Reads SpiderFoot CSV exports (CLI + Web UI formats)
│   ├── signals.py           # Extracts and classifies signals (SMOKING_GUN/STRONG/WEAK)
│   ├── network.py           # Builds NetworkX graph, Louvain clustering, hub detection
│   ├── pipeline.py          # Orchestrates the analysis workflow
│   ├── report.py            # Generates output reports (MD, CSV, GraphML)
│   ├── blacklist.py         # Domain blacklist management
│   └── visuals.py           # Network visualization
├── discovery/
│   ├── scraper.py           # Google/DuckDuckGo domain discovery
│   ├── scanner.py           # SpiderFoot batch scanning with progress tracking
│   ├── jobs.py              # Scan job queue management with persistence
│   ├── distributed.py       # C2 distributed scan controller (3,631 lines)
│   ├── worker_config.py     # Worker/scan configuration dataclasses (677 lines)
│   ├── spiderfoot_api.py    # SpiderFoot WebAPI integration
│   └── spiderfoot_control.py # SpiderFoot Control Center logic
├── ui/
│   ├── cyberpunk_hud.py     # Rich-based terminal HUD (main interface)
│   ├── cyberpunk_ui.py      # Themed submenu components (cyber_header, banners)
│   ├── gaming_hud.py        # Alternative gaming-style HUD
│   ├── integration.py       # Bridge between HUD and puppetmaster.py
│   ├── colors.py            # Color definitions
│   ├── ascii_art.py         # ASCII art assets
│   ├── components.py        # Reusable UI components
│   └── descriptions.py      # Menu item descriptions
├── kali/
│   ├── integration.py       # Kali Linux tool orchestration
│   ├── detect.py            # Kali environment detection
│   ├── modes.py             # Scan mode definitions (GHOST/STEALTH/STANDARD/DEEP)
│   ├── registry.py          # Tool registry and availability
│   ├── aggregator.py        # Results aggregation from multiple tools
│   ├── infra_analyzer.py    # Infrastructure correlation analysis
│   └── tools/               # Individual Kali tool wrappers (16 wrappers)
│       ├── theharvester.py  # Email/subdomain harvester
│       ├── amass.py         # DNS enumeration
│       ├── dnsrecon.py      # DNS reconnaissance
│       ├── dnsenum.py       # DNS zone enumeration
│       ├── nmap.py          # Port scanning
│       ├── nikto.py         # Web vulnerability scanning
│       ├── whatweb.py       # Web fingerprinting
│       ├── sslscan.py       # SSL/TLS analysis
│       ├── wafw00f.py       # WAF detection
│       ├── fierce.py        # DNS reconnaissance
│       ├── sublist3r.py     # Subdomain discovery
│       ├── metagoofil.py    # Metadata extraction
│       ├── exiftool.py      # File metadata analysis
│       ├── dmitry.py        # Deepmagic Information Tool
│       ├── sherlock.py      # Social media username search
│       └── base.py          # Base tool wrapper class
├── security/
│   └── audit.py             # Security audit module (615 lines)
├── wildcardDNS_analyzer.py  # Standalone wildcard DNS analyzer (1,946 lines)
├── infra_analysis.py        # Standalone infrastructure correlation (659 lines)
├── csv_keyword_cleaner.py   # CSV keyword filtering utility (269 lines)
├── upload.py                # EC2 deployment helper (778 lines)
├── config/                   # User configuration storage
├── domain_lists/             # Saved domain lists for reuse
└── output/                   # Where results are saved
```

---

## CYBERPUNK TERMINAL HUD

The main interface is a Rich-based terminal HUD with real-time updates:

```
╭─────────────────────────────────────────────────────────────────────╮
│ MISSION STATUS  Q:357 ██████  S:24 ████░░  C:3 ██░░░░  [SCANNING]   │
╰─────────────────────────────────────────────────────────────────────╯
╭─ LOADOUT ────────────────────╮  ╭─ ACTIVE MISSION ──────────────────╮
│  [1] Scrape domains          │  │  Mission description panel        │
│  [2] Load domains            │  │  with context-sensitive help      │
│ >[3] SpiderFoot Control Ctr  │  ╰───────────────────────────────────╯
│  [4] Check scan queue        │  ╭─ SYSTEM VITALS ───────────────────╮
╰──────────────────────────────╯  │  CPU/MEM/DISK real-time bars      │
                                  ╰───────────────────────────────────╯
```

**Key HUD Features:**
- Real-time system vitals (CPU/MEM/DISK via psutil)
- Live scan queue status
- Animated ASCII art banner
- Arrow key navigation + direct number input
- Automatic fallback to simple menu if Rich unavailable

---

## MAIN MENU STRUCTURE

```
DISCOVERY & SCANNING
[1] Scrape domains via keywords         # Google/DuckDuckGo search with blacklist
[2] Load domains from file              # Import from domain_lists/ directory
[3] SpiderFoot Control Center           # Submenu for scanning, GUI, DB management
[4] Check scan queue status             # Monitor progress, view stats

ANALYSIS
[5] Run Puppet Analysis                 # Full signal extraction + clustering
[6] View previous results               # Browse past analyses
[11] Signal//Noise Wildcard DNS filter  # Remove wildcard DNS domains

SETTINGS
[7] Configuration                       # Paths and settings
[8] Help & Documentation                # Full guide
[9] Launch in tmux                      # For long scans (survives disconnect)
[10] System monitor                     # Resource usage (via glances)

SECURITY
[S] Security Audit                      # Rootkit/backdoor detection (local + workers)

KALI ENHANCED MODE (when detected on Kali Linux):
[K1] Enumerate domain                   # Run all enabled Kali tools
[K2] Scan mode                          # Toggle: GHOST / STEALTH / STANDARD / DEEP
[K3] Tool status                        # Show available Kali tools
[K4] Blacklist (count)                  # Manage domain blacklist
[K5] Infra correlation                  # Cross-domain infrastructure analysis

[Q] Quit

SPIDERFOOT CONTROL CENTER [3] SUBMENU:
[1] Start Batch Scans                   # CLI batch mode with progress tracking
[2] View Scan Status                    # Monitor queue progress and stats
[3] Open Web GUI                        # Interactive browser interface
[4] Reset SpiderFoot DB                 # Clear SpiderFoot database
[5] Kill SpiderFoot                     # Stop running SpiderFoot processes
[I] Install SpiderFoot                  # Download and install SpiderFoot
[D] Multi-EC2 C2 Controller             # Distributed scanning submenu (see below)
[B] Back                                # Return to main menu

C2 DISTRIBUTED SCANNING [D] SUBMENU:

  WORKER MANAGEMENT
  [1] View Worker Status                # Detailed status of all workers
  [2] Add Worker                        # Add EC2 worker hostname
  [3] Remove Worker                     # Remove a worker from pool
  [4] Configure SSH Key                 # Set .pem key path
  [5] Setup Workers                     # Install SpiderFoot on all workers
  [6] EC2 Setup & Cost Guide            # Instance recommendations & launch commands
  [7] Replace Worker Addresses          # Update hostnames when EC2 instances restart

  SCAN OPERATIONS
  [S] Start Distributed Scan            # Launch scans across all workers
  [P] Check Progress                    # View real-time scan progress
  [A] Stop All Scans                    # Stop scans, restart GUIs for results
  [B] Abort All Scans                   # Kill everything immediately
  [V] View Aborted Domains              # Domains that timed out or failed
  [C] Collect Results                   # Download CSVs from all workers
  [G] GUI Access                        # SSH tunnel commands for worker GUIs
  [D] Debug Worker Logs                 # View worker scan logs

  DATABASE MANAGEMENT
  [R] Reset Worker Databases            # Wipe SpiderFoot DB on all workers
  [W] Verify Workers Clean              # Check workers have no running scans

  SECURITY
  [X] Security Audit                    # Scan for keys/creds on master & workers

  SETTINGS
  [M] Scan Mode                         # Toggle WebAPI (recommended) vs CLI mode
  [T] Scan Settings                     # Parallelism, timeouts, AWS region

  [Q] Back to Control Center
```

---

## DATA FLOW

```
SpiderFoot CSV Exports (CLI 3-col or Web UI 7-col format)
        │
        ▼
┌─────────────────┐
│   ingest.py     │  Reads CSVs, handles encoding issues, NUL bytes
│                 │  Auto-detects CLI vs Web UI format
│                 │  Extracts domain from filename for CLI format
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   signals.py    │  Extracts signals, classifies by tier:
│                 │  - SMOKING_GUN: Definitive proof (GA IDs, emails, SSL)
│                 │  - STRONG: Strong evidence (WHOIS, phones, nameservers)
│                 │  - WEAK: Filtered as noise (CDNs, cloud hosting)
│                 │
│                 │  Applies exclude patterns to filter false positives
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   network.py    │  Builds NetworkX weighted graph
│                 │  Runs Louvain community detection (REQUIRED: python-louvain)
│                 │  Calculates betweenness centrality, PageRank
│                 │  Identifies hub/controller domains
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   report.py     │  Generates:
│                 │  - executive_summary.md (human-readable)
│                 │  - smoking_guns.csv (definitive connections)
│                 │  - clusters.csv (domain groupings)
│                 │  - hub_analysis.csv (potential controllers)
│                 │  - network.graphml (for Gephi/other tools)
└─────────────────┘
```

---

## KEY DEPENDENCIES

```python
# REQUIRED (auto-installed via REQUIRED_PACKAGES check)
REQUIRED_PACKAGES = {
    'pandas': 'pandas',                    # Data manipulation
    'networkx': 'networkx',                # Graph analysis
    'tqdm': 'tqdm',                        # Progress bars
    'tldextract': 'tldextract',            # Domain parsing
    'matplotlib': 'matplotlib',            # Visualization
    'googlesearch': 'googlesearch-python', # Google search
    'ddgs': 'ddgs',                        # DuckDuckGo search
    'community': 'python-louvain',         # CRITICAL: Louvain clustering
    'dns': 'dnspython',                    # DNS resolution
    'simple_term_menu': 'simple-term-menu',# Domain review UI
    'rich': 'rich',                        # Terminal HUD
    'psutil': 'psutil',                    # System monitoring
}
```

**IMPORTANT:** `python-louvain` is required for accurate cluster detection. Without it, the tool falls back to label propagation which produces fewer, larger clusters.

---

## KALI LINUX INTEGRATION

When running on Kali Linux, PUPPETMASTER automatically detects and integrates with OSINT tools:

### Detected Tools

| Tool | Purpose | Available In |
|------|---------|-------------|
| theHarvester | Email/subdomain enumeration | GHOST, STEALTH, STANDARD, DEEP |
| Amass | Advanced DNS enumeration | STEALTH, STANDARD, DEEP |
| DNSRecon | DNS record analysis | STANDARD, DEEP |
| DNSEnum | DNS zone enumeration | DEEP |
| Sublist3r | Subdomain discovery | STANDARD, DEEP |
| Fierce | DNS reconnaissance | STANDARD, DEEP |
| WhatWeb | Web technology fingerprinting | STEALTH, STANDARD, DEEP |
| wafw00f | WAF detection | STANDARD, DEEP |
| SSLScan | SSL/TLS analysis | STEALTH, STANDARD, DEEP |
| Nmap | Port and service scanning | DEEP |
| Nikto | Web vulnerability scanning | DEEP |
| Metagoofil | Document metadata extraction | STANDARD, DEEP |
| ExifTool | File metadata analysis | GHOST, STEALTH, STANDARD, DEEP |
| DMitry | Deepmagic Information Tool | STANDARD, DEEP |
| Sherlock | Social media username search | DEEP |

### Scan Modes

| Mode | Description | Target Contact | Detection Risk |
|------|-------------|----------------|----------------|
| **GHOST** | Passive only — zero target contact | None | None |
| **STEALTH** | Light touch — 1-2 requests per domain | Minimal | Low |
| **STANDARD** | Balanced reconnaissance (default) | Moderate | Medium |
| **DEEP** | Maximum coverage — high noise | High | High |

- **GHOST**: Only passive tools (theHarvester passive, exiftool). No SpiderFoot, no Nmap.
- **STEALTH**: Adds amass, whatweb, sslscan. Still no SpiderFoot or Nmap.
- **STANDARD**: Enables SpiderFoot integration and most tools. No Nmap.
- **DEEP**: Everything enabled including Nmap, Nikto, DNSEnum, Sherlock, subdomain brute-forcing.

### Infrastructure Correlation (K5)

Cross-references results from multiple Kali tools using weighted correlation signals:

| Signal | Weight | Meaning |
|--------|--------|---------|
| shared_ssl_fingerprint | 1.0 | Exact same SSL certificate |
| shared_email | 0.95 | Same contact email |
| shared_social_username | 0.95 | Same username on social platforms |
| shared_ip | 0.9 | Multiple domains resolve to same IP |
| shared_author | 0.9 | Same document author (via metagoofil/exiftool) |
| shared_ssl_org | 0.85 | Same organization in SSL certificate |
| shared_mx | 0.8 | Same mail server |
| shared_nameserver | 0.7 | Same NS records |
| shared_email_domain | 0.7 | Emails from same custom domain |
| shared_ip_range | 0.6 | Domains in same /24 subnet |
| shared_tech_stack | 0.5 | Identical CMS/framework/version |
| shared_server_signature | 0.4 | Identical web server version/config |
| shared_ssl_issuer | 0.3 | Same certificate issuer |
| shared_creator_tool | 0.3 | Same document creation software |

---

## JOB TRACKING SYSTEM

### discovery/jobs.py

Manages scan queue with persistence:

```python
class JobTracker:
    """Persists to .working_set.json"""
    - add_domains(domains: List[str])  # Add to queue
    - get_pending() -> List[ScanJob]   # Get pending jobs
    - get_stats() -> dict              # Queue statistics
    - has_pending_work() -> bool       # Check if work remains
```

### Domain Sanitization

```python
def sanitize_domain(domain: str) -> Optional[str]:
    """
    - Removes protocols (http://, https://)
    - Removes paths and query strings
    - Removes port numbers
    - Validates format
    """
```

---

## SIGNAL CLASSIFICATION SYSTEM

### Tier 1: SMOKING_GUN (Definitive Proof)

These signals **definitively prove** same ownership. One match = same operator.

| Signal Type | Example | Why Definitive |
|-------------|---------|----------------|
| `google_analytics` | UA-12345678-1 | Unique per GA account |
| `adsense` | pub-1234567890 | Unique per AdSense account |
| `google_site_verification` | Token string | Unique per Search Console account |
| `email` | specific@domain.com | Operator's actual email |
| `ssl_fingerprint` | SHA256 hash | Custom SSL certificate |

### Tier 2: STRONG (High Confidence)

Multiple matches suggest connection but could be coincidental.

| Signal Type | Example | Notes |
|-------------|---------|-------|
| `whois_registrant` | "John Doe, 123 Main St" | WHOIS registration info |
| `phone` | +1-555-123-4567 | Contact phone numbers |
| `nameserver` | ns1.customdns.com | Custom nameservers only |
| `ip_address` | 192.168.1.1 | Shared hosting IPs |
| `crypto_address` | bc1q... | Bitcoin/crypto addresses |

### Tier 3: WEAK (Filtered as Noise)

These are excluded to prevent false positives.

| Pattern | Why Excluded |
|---------|--------------|
| Cloudflare IPs | Shared CDN infrastructure |
| AWS/Azure/GCP IPs | Shared cloud hosting |
| Registrar abuse emails | Generic contacts |
| Common nameservers | ns1.google.com, etc. |

---

## SPIDERFOOT INTEGRATION

### SpiderFoot CLI Scanning (Option [3] → Start Batch Scans)

```python
# Runs SpiderFoot in background with progress tracking
# Command: python3 sf.py -s domain.com -o csv -q
# Output: exports/domain_com_YYYYMMDD_HHMMSS.csv
```

### SpiderFoot Web GUI (Option [3] → Open Web GUI)

```python
# Launches SpiderFoot web interface in tmux session
# Command: python3 sf.py -l 127.0.0.1:5001
# Session name: "spiderfoot-gui"
# Access via SSH tunnel for remote servers
```

### CSV Format Detection

The tool auto-detects two formats:

**CLI Format (3 columns):**
```csv
Source,Type,Data
example.com,IP Address,192.168.1.1
```

**Web UI Format (7 columns):**
```csv
Scan Name,Updated,Type,Module,Source,F/P,Data
example.com,2024-01-01 12:00,IP Address,sfp_dnsresolve,example.com,0,192.168.1.1
```

---

## CONFIGURATION SYSTEM

### config.json

```json
{
    "spiderfoot_path": "/path/to/spiderfoot",
    "output_dir": "./output",
    "keywords": ["industry keyword", "competitor name"],
    "pending_domains": ["domain1.com", "domain2.com"],
    "blacklist_count": 231
}
```

### domain_lists/

Saved domain lists for reuse:
```
domain_lists/
├── scrape_2024-01-01_keywords.txt
├── my_targets.txt
└── ...
```

---

## OUTPUT FILES EXPLAINED

| File | Contents |
|------|----------|
| `executive_summary.md` | Human-readable overview with key findings |
| `smoking_guns.csv` | All definitive connections with evidence |
| `clusters.csv` | Domain cluster assignments with confidence |
| `hub_analysis.csv` | Potential controller/C2 domains |
| `all_connections.csv` | Complete connection list |
| `signals.csv` | All extracted signals |
| `network.graphml` | Graph file for Gephi/Cytoscape visualization |

---

## REMOTE SERVER SUPPORT

### SSH Tunnel for Web GUI

When running on EC2/VPS, the tool:
1. Detects SSH connection via `$SSH_CONNECTION` environment variable
2. Attempts to get public IP from EC2 metadata API
3. Displays SSH tunnel command for user:

```bash
ssh -L 5001:localhost:5001 user@server
```

### tmux Integration

Option [9] launches PUPPETMASTER in tmux session "puppetmaster":
- Survives SSH disconnects
- Domains loaded before tmux persist via config.json
- Detach: `Ctrl+b, d`
- Reattach: `tmux attach -t puppetmaster`

---

## COMMON ANALYSIS TASKS

### "Show me all domains connected to X"

```bash
grep "targetdomain.com" smoking_guns.csv
```

### "What evidence links domain A to domain B?"

```bash
grep "domainA.com.*domainB.com\|domainB.com.*domainA.com" smoking_guns.csv
```

### "Find the main operator"

Look in `hub_analysis.csv` for domains with:
- Highest `smoking_guns` count
- Highest `centrality` score
- These are likely the central controller domains

---

## FALSE POSITIVE AWARENESS

The tool filters many false positives, but some may slip through:

### Legitimate Shared Services

| Pattern | Why It Might Be False Positive |
|---------|-------------------------------|
| Same web developer | Agency built multiple client sites |
| Same hosting reseller | Shared infrastructure, different owners |
| Same WordPress theme | Common templates |

### How to Verify

1. Check if the shared signal is truly unique (specific GA ID vs. generic email)
2. Look for multiple independent signals connecting the same domains
3. Manual review of the actual websites

---

## SECURITY NOTES

- All file operations are read-only on input, write-only to output directory
- Network calls limited to: search engines (discovery), DNS (resolution), EC2 metadata (IP detection), SpiderFoot WebAPI (scan submission/progress on workers)
- Kali tools run with user permissions only
- No shell injection - all subprocess calls use argument lists
- No user credentials accessed
- Safe to run on untrusted SpiderFoot data

---

## DISTRIBUTED SCANNING (C2 CONTROLLER)

For large-scale scanning (100-500+ domains), PUPPETMASTER includes a distributed C2 controller:

```
discovery/
├── distributed.py         # Main C2 controller (3,631 lines)
├── worker_config.py       # Configuration dataclasses (677 lines)
└── spiderfoot_api.py      # WebAPI integration for parallel scanning
```

**Access:** SpiderFoot Control Center → [D] Multi-EC2 C2 Controller

### Key Classes

| Class | Purpose |
|-------|---------|
| `SSHExecutor` | Executes commands on remote workers via SSH subprocess |
| `ResourceDetector` | Detects worker RAM/CPU to recommend optimal parallelism |
| `SpiderFootInstaller` | Installs SpiderFoot and dependencies on remote workers |
| `DomainDistributor` | Splits domains evenly across available workers |
| `DistributedScanController` | Main orchestrator — scan submission, progress monitoring, result collection |

### WebAPI vs CLI Scan Mode

| | **WebAPI** (recommended) | **CLI** |
|--|--------------------------|---------|
| How it works | Uses SpiderFoot's web server + REST API | Runs `sf.py -s domain -o csv` per scan |
| Parallelism | Up to 50 scans per worker | Up to 10 scans per worker |
| Queue model | Rolling queue — submits new scans as slots open | Serial bash scripts |
| Result collection | Downloads CSVs from SpiderFoot web interface | Copies CSV files via scp |
| Default | Yes (recommended) | Legacy mode |

Toggle with C2 menu → [M] Scan Mode.

### DistributedConfig Fields

```python
@dataclass
class DistributedConfig:
    # SSH
    ssh_key_path: str                    # Path to .pem file
    ssh_timeout: int = 30                # SSH connection timeout (seconds)
    use_ssh_agent: bool = True           # Use ssh-agent (RECOMMENDED)

    # Workers
    workers: List[WorkerConfig]          # Worker pool

    # Remote paths
    remote_work_dir: str = "~/sf_distributed"
    spiderfoot_install_dir: str = "~/spiderfoot"

    # AWS
    aws_region: str = "us-east-1"        # Configurable via Settings

    # Scan settings
    parallel_scans_per_worker: int       # Auto-detected from worker RAM
    hard_timeout_hours: float = 6.0      # Hard timeout per scan
    activity_timeout_minutes: int = 60   # Inactivity timeout
    scan_mode: str = "webapi"            # "webapi" or "cli"
    master_output_dir: str = "./distributed_results"

    # Session tracking
    aborted_domains: List[str]           # Domains that failed/timed out
    current_session_id: Optional[str]    # Active session ID
    total_domains_in_session: int        # Total domains in session
```

### Operational Notes

- **Fresh start sequence:** Always run Reset Worker Databases → Setup Workers → Verify Workers Clean before starting a new scanning session
- **Master must stay running** to manage the rolling scan queue
- **If a worker connection is lost**, the queue pauses for that worker (fails safe)
- **Process counts:** Setting "5 concurrent scans" per worker produces MORE than 5 Python processes — SpiderFoot spawns internal workers per scan

---

## SECURITY AUDIT MODULE

**Access:** Main menu → [S] Security Audit, or C2 menu → [X] Security Audit

The security audit module (`security/audit.py`, 615 lines) scans for rootkits, backdoors, and system compromises.

### Tools Used

| Tool | Purpose |
|------|---------|
| chkrootkit | Rootkit signature detection |
| rkhunter | Rootkit hunter + backdoor detection |
| lynis | Full security audit |
| debsums | Package integrity verification |
| unhide | Hidden process/port detection |

### Capabilities

- Audit **local machine** or **all distributed workers** (via SSH)
- Auto-install missing audit tools
- Clear disclaimer about detection limitations

### Limitations

- Detects known rootkits and backdoors
- **Cannot** detect supply chain attacks, credential theft, or novel rootkits
- Not a replacement for full incident response

---

## WILDCARD DNS ANALYZER

**Access:** Main menu → [11], or standalone: `python3 wildcardDNS_analyzer.py --domain example.com`

The wildcard DNS analyzer (`wildcardDNS_analyzer.py`, 1,946 lines) filters out domains using wildcard/catch-all DNS, which are typically:
- Parked domain services
- Domain squatters
- Hosting providers with catch-all DNS records

These domains generate false positives in analysis because any subdomain resolves to the same IP, making infrastructure-sharing signals meaningless.

**Integrated mode:** Filters domains before puppet analysis (menu option [11])
**Standalone mode:** Run directly for batch DNS analysis

---

## INFRASTRUCTURE ANALYSIS (STANDALONE)

**Access:** `python3 infra_analysis.py`

Standalone cross-domain infrastructure correlation tool (659 lines). Separate from K5 (Kali infra correlation) — this one works **without** Kali Linux.

Analyzes domains for shared infrastructure indicators:
- Shared IP addresses
- Shared SSL certificates
- Shared nameservers
- Shared technology stacks

Use as a supplementary detection method alongside the main puppet analysis pipeline.

---

## KNOWN LIMITATIONS

### Thread Safety
- Background scan stats use `_background_scan_lock` for thread safety
- Worker config updates use file locking to prevent corruption
- Rapid clicks can be prevented by checking `is_background_scan_running()`

### Memory Usage
- CSV data is loaded entirely into memory
- Large datasets (1M+ rows) may require more RAM
- Consider batch processing for very large inputs

### Python Version
- Requires Python 3.9+ (uses modern type hints like `list[str]` instead of `List[str]`)
- Code uses dataclasses extensively

### Optional Dependencies
- `python-louvain` is required for community detection (clustering)
- If missing, clustering features will not work correctly
- Install with: `pip install python-louvain`

---

## QUESTIONS AI AGENTS MIGHT BE ASKED

1. **"Is this domain connected to others?"** - Check smoking_guns.csv and clusters.csv
2. **"Who operates this network?"** - Look at hub_analysis.csv for central domains
3. **"How confident is this connection?"** - SMOKING_GUN = definitive, STRONG = high confidence
4. **"Could this be a false positive?"** - Check if signal is infrastructure-level vs. operator-level
5. **"What should I investigate next?"** - Hub domains with high centrality
6. **"How do I scan domains remotely?"** - Option [9] (tmux) + Option [3] → Open Web GUI with SSH tunnel
7. **"Why are there fewer clusters than expected?"** - Check if python-louvain is installed
8. **"Why doesn't the Kali menu show?"** - Only appears when running on Kali Linux with tools installed
9. **"Where are my scraped domains?"** - In config.json `pending_domains` or saved in `domain_lists/`
10. **"How do I resume after disconnect?"** - `tmux attach -t puppetmaster`
11. **"How do I scan 100+ domains faster?"** - Use distributed scanning: [D] Multi-EC2 C2 Controller
12. **"How do I reset worker databases?"** - C2 menu → [R] Reset Worker Databases
13. **"How do I review/delete domains before scanning?"** - Load domains → [R] Review & remove domains
14. **"How do I switch to WebAPI mode?"** - C2 menu → [M] Scan Mode → select WebAPI. It's the default and recommended mode (5x more parallelism than CLI)
15. **"Why are only N scans running when I set more?"** - Worker RAM limits parallelism. ResourceDetector auto-detects optimal count. In WebAPI mode, max 50/worker; CLI mode, max 10/worker
16. **"How do I run infrastructure analysis?"** - Standalone: `python3 infra_analysis.py`. Or use [K5] on Kali for the integrated version with weighted correlation signals
17. **"What's the difference between K5 and infra_analysis.py?"** - K5 uses Kali tool results; infra_analysis.py runs independently without Kali

---

*This document was created to help AI coding assistants understand and work with the PUPPETMASTER codebase effectively.*

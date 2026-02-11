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
puppetmaster.py              # Main entry point, interactive CLI menu (5300+ lines)
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
│   └── jobs.py              # Scan job queue management with persistence
├── ui/
│   ├── cyberpunk_hud.py     # Rich-based terminal HUD (main interface)
│   ├── gaming_hud.py        # Alternative gaming-style HUD
│   ├── integration.py       # Bridge between HUD and puppetmaster.py
│   ├── colors.py            # Color definitions
│   ├── ascii_art.py         # ASCII art assets
│   ├── components.py        # Reusable UI components
│   └── descriptions.py      # Menu item descriptions
├── kali/
│   ├── integration.py       # Kali Linux tool orchestration
│   ├── detect.py            # Kali environment detection
│   ├── modes.py             # Scan mode definitions (STANDARD/ENHANCED/STEALTH)
│   ├── registry.py          # Tool registry and availability
│   ├── aggregator.py        # Results aggregation from multiple tools
│   ├── infra_analyzer.py    # Infrastructure correlation analysis
│   └── tools/               # Individual Kali tool wrappers
│       ├── theharvester.py  # Email/subdomain harvester
│       ├── amass.py         # DNS enumeration
│       ├── dnsrecon.py      # DNS reconnaissance
│       ├── nmap.py          # Port scanning
│       ├── whatweb.py       # Web fingerprinting
│       └── ...              # More tool wrappers
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
[Q] Quit

SPIDERFOOT CONTROL CENTER [3] SUBMENU:
[1] Start Batch Scans                   # CLI batch mode with progress tracking
[2] View Scan Status                    # Monitor queue progress and stats
[3] Open Web GUI                        # Interactive browser interface
[4] Reset SpiderFoot DB                 # Clear SpiderFoot database
[5] Kill SpiderFoot                     # Stop running SpiderFoot processes
[I] Install SpiderFoot                  # Download and install SpiderFoot
[B] Back                                # Return to main menu

KALI TOOLS (when detected on Kali Linux):
[K1] Enumerate domain                   # Run all enabled Kali tools
[K2] Scan mode [STANDARD/ENHANCED]      # Toggle tool intensity
[K3] Tool status                        # Show available Kali tools
[K4] Blacklist (count)                  # Manage domain blacklist
[K5] Infra correlation                  # Cross-domain infrastructure analysis
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

| Tool | Purpose | Mode |
|------|---------|------|
| theHarvester | Email/subdomain enumeration | STANDARD |
| Amass | Advanced DNS enumeration | ENHANCED |
| DNSRecon | DNS record analysis | STANDARD |
| Sublist3r | Subdomain discovery | STANDARD |
| Fierce | DNS reconnaissance | STANDARD |
| WhatWeb | Web technology fingerprinting | STANDARD |
| wafw00f | WAF detection | STANDARD |
| SSLScan | SSL/TLS analysis | STANDARD |
| Nmap | Port scanning | ENHANCED |
| Nikto | Web vulnerability scanning | ENHANCED |

### Scan Modes

- **STANDARD**: Safe tools, no aggressive scanning
- **ENHANCED**: Includes nmap and nikto (more intrusive)
- **STEALTH**: Rate-limited, minimal footprint

### Infrastructure Correlation (K5)

Cross-references results from multiple tools to find:
- Shared IP addresses across domains
- Common nameservers
- Related subdomains
- Certificate overlaps

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
- Network calls limited to: search engines (discovery), DNS (resolution), EC2 metadata (IP detection)
- Kali tools run with user permissions only
- No shell injection - all subprocess calls use argument lists
- No user credentials accessed
- Safe to run on untrusted SpiderFoot data

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

---

*This document was created to help AI coding assistants understand and work with the PUPPETMASTER codebase effectively.*

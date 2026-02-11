# PUPPETMASTER - Technical Reference for AI Agents

**Purpose of this document:** This file provides a comprehensive technical overview for AI coding assistants (Claude, GPT, Cursor, etc.) to quickly understand the codebase, verify its safety, and help users interpret results.

---

## QUICK SAFETY CHECK

This tool is **read-only analysis software**. It:
- Does NOT modify any files outside its output directory
- Does NOT execute arbitrary code
- Does NOT access credentials or sensitive data
- Only reads CSV files and writes analysis reports
- Network requests are limited to: Google/DuckDuckGo searches (for domain discovery) and EC2 metadata API (to detect public IP)

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
puppetmaster.py              # Main entry point, interactive CLI menu
├── core/
│   ├── ingest.py            # Reads SpiderFoot CSV exports (CLI + Web UI formats)
│   ├── signals.py           # Extracts and classifies signals (SMOKING_GUN/STRONG/WEAK)
│   ├── network.py           # Builds NetworkX graph, Louvain clustering, hub detection
│   ├── pipeline.py          # Orchestrates the analysis workflow
│   └── report.py            # Generates output reports (MD, CSV, GraphML)
├── discovery/
│   ├── scraper.py           # Google/DuckDuckGo domain discovery
│   └── scanner.py           # SpiderFoot batch scanning with progress tracking
├── utils/
│   ├── display.py           # Terminal colors, spinners, animations
│   └── progress.py          # Progress tracking for long scans
├── config/                   # User configuration storage
└── output/                   # Where results are saved
```

---

## MAIN MENU STRUCTURE

```
DISCOVERY & SCANNING
[1]  Scrape domains via keywords        # Google/DuckDuckGo search
[2]  Load domains from file             # Import domain list (.txt, one per line)
[3]  Run SpiderFoot scans (CLI)         # Batch mode, runs in background
[4]  Check scan queue status            # Monitor progress, view stats
[11] SpiderFoot Web GUI                 # Interactive browser interface

ANALYSIS
[5]  Run Puppet Analysis                # Full signal extraction + clustering
[6]  View previous results              # Browse past analyses

SETTINGS
[7]  Configuration                      # Paths and settings
[8]  Help & Documentation               # Full guide
[9]  Launch in tmux                     # For long scans (survives SSH disconnect)
[10] System monitor                     # Resource usage (glances)
[q]  Quit
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
# REQUIRED (auto-installed)
REQUIRED_PACKAGES = {
    'pandas': 'pandas',
    'networkx': 'networkx',
    'tqdm': 'tqdm',
    'tldextract': 'tldextract',
    'matplotlib': 'matplotlib',
    'googlesearch': 'googlesearch-python',
    'ddgs': 'ddgs',
    'community': 'python-louvain',  # CRITICAL for accurate clustering
}

# OPTIONAL (enhances functionality)
OPTIONAL_PACKAGES = {
    'scipy': 'scipy',  # PageRank calculations (falls back to degree centrality)
}
```

**IMPORTANT:** `python-louvain` is required for accurate cluster detection. Without it, the tool falls back to label propagation which produces fewer, larger clusters.

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

### SpiderFoot CLI Scanning (Option 3)

```python
# Runs SpiderFoot in background with progress tracking
# Command: python3 sf.py -s domain.com -o csv -q
# Output: exports/domain_com_YYYYMMDD_HHMMSS.csv
```

### SpiderFoot Web GUI (Option 11)

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

Option 9 launches PUPPETMASTER in tmux session "puppetmaster":
- Survives SSH disconnects
- Detach: `Ctrl+b, d`
- Reattach: `tmux attach -t puppetmaster`

Option 11 launches SpiderFoot GUI in tmux session "spiderfoot-gui":
- Separate session from main PUPPETMASTER
- Can run both simultaneously

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

## HOW TO INTERPRET RESULTS

### Reading `smoking_guns.csv`

```csv
domain1,domain2,signal_type,signal_value,description,module
example1.com,example2.com,google_analytics,UA-12345-1,Google Analytics ID,sfp_webanalytics
```

**Interpretation:** example1.com and example2.com share Google Analytics ID UA-12345-1, proving same operator.

### Reading `clusters.csv`

```csv
cluster_id,confidence,size,hub_domain,smoking_gun_count,domains
1,HIGH,15,mainsite.com,234,"site1.com; site2.com; site3.com..."
```

**Interpretation:** Cluster 1 contains 15 domains, likely controlled by mainsite.com, with 234 definitive connections.

### Reading `hub_analysis.csv`

```csv
domain,total_connections,smoking_guns,likely,centrality
controller.com,186,121,51,0.028
```

**Interpretation:** controller.com has 186 total connections, 121 definitive. High centrality suggests potential command/control domain.

### Confidence Levels

- **CONFIRMED** - At least one smoking gun signal
- **LIKELY** - Multiple strong signals (2+)
- **POSSIBLE** - One strong signal
- **WEAK** - Only weak/supporting signals

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

### "Are these two clusters connected?"

Look for domains that appear in both clusters, or shared signals between cluster hub domains.

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

## EXTENDING THE TOOL

### Adding New Signal Types

In `core/signals.py`, add to `SIGNAL_CONFIG`:

```python
'new_signal_type': {
    'tier': SignalTier.SMOKING_GUN,  # or STRONG or WEAK
    'patterns': [r'regex_pattern'],
    'exclude_patterns': [r'patterns_to_ignore'],
    'spiderfoot_types': ['SpiderFoot Type Name'],
}
```

### Adding New Exclusions

If you encounter false positives, add patterns to the relevant `exclude_patterns` list in `core/signals.py`.

---

## SECURITY NOTES

- All file operations are read-only on input, write-only to output directory
- Network calls limited to: search engines (discovery), EC2 metadata (IP detection)
- No shell commands executed except SpiderFoot itself
- No user credentials accessed
- Safe to run on untrusted SpiderFoot data

---

## QUESTIONS AI AGENTS MIGHT BE ASKED

1. **"Is this domain connected to others?"** - Check smoking_guns.csv and clusters.csv
2. **"Who operates this network?"** - Look at hub_analysis.csv for central domains
3. **"How confident is this connection?"** - SMOKING_GUN = definitive, STRONG = high confidence
4. **"Could this be a false positive?"** - Check if signal is infrastructure-level vs. operator-level
5. **"What should I investigate next?"** - Hub domains with high centrality
6. **"How do I scan domains remotely?"** - Option 9 (tmux) + Option 11 (Web GUI) with SSH tunnel
7. **"Why are there fewer clusters than expected?"** - Check if python-louvain is installed

---

*This document was created to help AI coding assistants understand and work with the PUPPETMASTER codebase effectively.*

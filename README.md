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
│  SPIDERFOOT CONTROL CENTER [3]:          │  ╰───────────────────────────────────────────────╯
│  ──────────────────────────              │  ╭───────────────────────────────────────────────╮
│   [1] Start Batch Scans                  │  │  ██████╗ ██╗   ██╗██████╗ ██████╗ ███████╗    │
│   [2] View Scan Status                   │  │  ██╔══██╗██║   ██║██╔══██╗██╔══██╗██╔════╝    │
│   [3] Open Web GUI                       │  │  ██████╔╝██║   ██║██████╔╝██████╔╝█████╗      │
│   [4] Reset SpiderFoot DB                │  │  ██╔═══╝ ██║   ██║██╔═══╝ ██╔═══╝ ██╔══╝      │
│   [5] Kill SpiderFoot                    │  │  ██║     ╚██████╔╝██║     ██║     ███████╗    │
│   [I] Install SpiderFoot                 │  │  ╚═╝      ╚═════╝ ╚═╝     ╚═╝     ╚══════╝    │
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

- Python 3.8 or higher
- SpiderFoot (auto-installed if not present)

### Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/puppetmaster.git
cd puppetmaster

# Run PUPPETMASTER (auto-installs dependencies)
python3 puppetmaster.py
```

That's it! The Cyberpunk HUD launches automatically and guides you through everything.

### Platform-Specific Notes

**Linux (Ubuntu/Debian/Kali):**
```bash
# If needed, install Python and pip:
sudo apt update && sudo apt install python3 python3-pip python3-venv
```

**Kali Linux:** Automatically detects and enables additional OSINT tools (theHarvester, Amass, DNSRecon, etc.)

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

## Kali Linux Integration

When running on Kali Linux, PUPPETMASTER automatically detects and integrates with additional OSINT tools:

| Tool | Purpose |
|------|---------|
| theHarvester | Email and subdomain enumeration |
| Amass | Advanced DNS enumeration |
| DNSRecon | DNS record analysis |
| Sublist3r | Subdomain discovery |
| Fierce | DNS reconnaissance |
| WhatWeb | Web technology fingerprinting |
| wafw00f | WAF detection |
| SSLScan | SSL/TLS analysis |
| Nmap | Port and service scanning |

These tools are automatically detected and integrated when running on Kali Linux.

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

Tested with 100+ domains / 13 million SpiderFoot rows. Larger datasets work but take longer.

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

## Issues & Contributing

Found a bug? Have an idea? Open an issue on GitHub.

Pull requests welcome!

---

*PUPPETMASTER - Because sock puppets should be on children's shows, not the internet.*

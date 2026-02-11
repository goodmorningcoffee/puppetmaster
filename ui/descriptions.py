"""
PUPPETMASTER Tool Descriptions
All menu items and their detailed descriptions for the Mission Panel
"""

from dataclasses import dataclass
from typing import List, Optional

@dataclass
class ToolDescription:
    """Description for a single tool/menu item"""
    key: str                    # "01", "K1", etc.
    emoji: str                  # Display emoji
    short_name: str             # Short menu label
    title: str                  # Full title for mission panel
    subtitle: str               # Subtitle in mission panel
    description: List[str]      # Multi-line description paragraphs
    objectives: List[str]       # Bullet points
    next_step: Optional[str]    # "Next: ..." hint
    category: str               # DISCOVERY, ANALYSIS, ADVANCED, SETTINGS

# Menu items for navigation (order matters!)
MENU_ITEMS = [
    # DISCOVERY & SCANNING
    ("01", "DISCOVERY & SCANNING"),
    ("02", "DISCOVERY & SCANNING"),
    ("03", "DISCOVERY & SCANNING"),
    ("04", "DISCOVERY & SCANNING"),
    # ANALYSIS
    ("05", "ANALYSIS"),
    ("06", "ANALYSIS"),
    ("11", "ANALYSIS"),  # Wildcard DNS moved from 12
    # ADVANCED TOOLS (Kali)
    ("K1", "ADVANCED TOOLS"),
    ("K2", "ADVANCED TOOLS"),
    ("K3", "ADVANCED TOOLS"),
    ("K4", "ADVANCED TOOLS"),
    ("K5", "ADVANCED TOOLS"),
    # SETTINGS
    ("07", "SETTINGS"),
    ("08", "SETTINGS"),
    ("09", "SETTINGS"),
    ("10", "SETTINGS"),
    # QUIT
    ("Q", "QUIT"),
]

# Get ordered list of tool keys (excluding Q)
TOOL_ORDER = [key for key, _ in MENU_ITEMS if key != "Q"]

# Full tool descriptions
TOOL_DESCRIPTIONS = {
    "01": ToolDescription(
        key="01",
        emoji="🔍",
        short_name="Scrape domains (keywords)",
        title="KEYWORD SCRAPE",
        subtitle="Search Engine Domain Discovery",
        description=[
            "Scrape Google and DuckDuckGo using industry keywords to discover",
            "competitor domains that might be sock puppets. This is typically",
            "the first step in the workflow.",
        ],
        objectives=[
            "Keywords loaded from config.json",
            "Results filtered through blacklist",
            "Output added to pending queue for scanning",
            "Expected runtime: ~2-5 minutes",
        ],
        next_step="Use [3] to scan discovered domains with SpiderFoot",
        category="DISCOVERY & SCANNING",
    ),

    "02": ToolDescription(
        key="02",
        emoji="📂",
        short_name="Load domains (file)",
        title="LOAD DOMAINS",
        subtitle="Import Target List from File",
        description=[
            "Import a list of target domains from a text file. Use this if you",
            "already have a list of domains to investigate instead of scraping",
            "search engines. One domain per line.",
        ],
        objectives=[
            "Read domains from specified text file",
            "Validate domain format",
            "Filter through blacklist",
            "Add to pending queue for scanning",
        ],
        next_step="Use [3] to scan imported domains with SpiderFoot",
        category="DISCOVERY & SCANNING",
    ),

    "03": ToolDescription(
        key="03",
        emoji="🕷️",
        short_name="SpiderFoot Control Center",
        title="SPIDERFOOT CONTROL CENTER",
        subtitle="Unified Scanning & Database Management",
        description=[
            "Unified control center for all SpiderFoot operations. Start batch",
            "scans with intensity presets, launch the Web GUI, manage the",
            "database, and monitor scan progress with ETA tracking.",
        ],
        objectives=[
            "Start batch scans (Safe/Moderate/Committed presets)",
            "Launch Web GUI for interactive scanning",
            "Reset SpiderFoot database (wipe zombie scans)",
            "Kill stuck SpiderFoot processes",
            "ETA tracking for long scan batches",
        ],
        next_step="Use [5] to analyze scans for sock puppet clusters",
        category="DISCOVERY & SCANNING",
    ),

    "04": ToolDescription(
        key="04",
        emoji="📋",
        short_name="Check scan queue",
        title="SCAN QUEUE STATUS",
        subtitle="View and Manage Domain Queue",
        description=[
            "View the current scan queue, see which domains are pending,",
            "in progress, or completed. Remove domains or reprioritize",
            "the queue as needed.",
        ],
        objectives=[
            "View pending domains",
            "Check in-progress scans",
            "Review completed scans",
            "Remove or reprioritize domains",
        ],
        next_step=None,
        category="DISCOVERY & SCANNING",
    ),

    "11": ToolDescription(
        key="11",
        emoji="📡",
        short_name="Wildcard DNS Analyzer",
        title="WILDCARD DNS ANALYZER",
        subtitle="Signal//Noise Filter for False Positives",
        description=[
            "Filter out false positives caused by wildcard DNS configurations.",
            "Some hosting providers return results for any subdomain, which can",
            "create noise in your analysis. This tool identifies and filters them.",
        ],
        objectives=[
            "Detect wildcard DNS responses",
            "Filter false positive subdomains",
            "Improve signal-to-noise ratio",
            "Clean up scan results",
        ],
        next_step=None,
        category="ANALYSIS",
    ),

    "05": ToolDescription(
        key="05",
        emoji="🎭",
        short_name="Puppet Analysis",
        title="PUPPET ANALYSIS",
        subtitle="Cluster Detection via Shared Identifiers",
        description=[
            "Analyze completed SpiderFoot scans to detect sock puppet clusters.",
            "Finds domains that share unique identifiers like Google Analytics",
            "IDs, AdSense IDs, or other tracking codes.",
        ],
        objectives=[
            "Same Google Analytics/AdSense IDs (strong indicator)",
            "Same WHOIS registrant info (strong evidence)",
            "Same nameservers or hosting (supporting evidence)",
            "Same SSL certificate details (supporting evidence)",
        ],
        next_step="Note: Shared identifiers are strong indicators, not proof",
        category="ANALYSIS",
    ),

    "06": ToolDescription(
        key="06",
        emoji="📊",
        short_name="View results",
        title="VIEW RESULTS",
        subtitle="Explore Detected Puppet Networks",
        description=[
            "Browse previously detected sock puppet clusters. View which",
            "domains are connected, what identifiers they share, and the",
            "confidence level of each connection.",
        ],
        objectives=[
            "View detected clusters",
            "See shared identifiers",
            "Export reports",
            "Deep dive analysis",
        ],
        next_step=None,
        category="ANALYSIS",
    ),

    # Note: "12" is kept for backward compatibility, redirects to "11"
    "12": ToolDescription(
        key="12",
        emoji="📡",
        short_name="Wildcard DNS Analyzer",
        title="WILDCARD DNS ANALYZER",
        subtitle="Signal//Noise Filter (Alias for [11])",
        description=[
            "This option has been moved to [11]. Both keys work identically.",
        ],
        objectives=[],
        next_step="Same as [11]",
        category="ANALYSIS",
    ),

    "K1": ToolDescription(
        key="K1",
        emoji="🔧",
        short_name="Enumerate domain",
        title="DOMAIN ENUMERATION",
        subtitle="Subdomain & Infrastructure Discovery",
        description=[
            "Run comprehensive enumeration on a single domain using multiple",
            "tools: theHarvester, amass, sublist3r, and fierce. Discovers",
            "subdomains, related infrastructure, and exposed services.",
        ],
        objectives=[
            "theHarvester - OSINT data gathering",
            "amass - Attack surface mapping",
            "sublist3r - Subdomain enumeration",
            "fierce - DNS reconnaissance",
        ],
        next_step="Input: Single target domain",
        category="ADVANCED TOOLS",
    ),

    "K2": ToolDescription(
        key="K2",
        emoji="⚙️",
        short_name="Scan mode",
        title="SCAN MODE CONFIGURATION",
        subtitle="Adjust Scan Intensity",
        description=[
            "Change the scan mode to balance between stealth and thoroughness.",
            "Higher modes find more data but take longer and are more detectable.",
        ],
        objectives=[
            "GHOST (20) - Minimal footprint, basic data only",
            "STEALTH (25) - Low profile, essential modules",
            "STANDARD (30) - Balanced approach",
            "DEEP (35) - Thorough scan, all modules",
        ],
        next_step=None,
        category="ADVANCED TOOLS",
    ),

    "K3": ToolDescription(
        key="K3",
        emoji="📋",
        short_name="Tool status",
        title="TOOL STATUS",
        subtitle="Check Available Advanced Tools",
        description=[
            "Check which advanced tools are installed and available on your",
            "system. Shows version info and any missing dependencies.",
        ],
        objectives=[
            "theHarvester status",
            "amass status",
            "sublist3r status",
            "fierce status",
            "SpiderFoot status",
        ],
        next_step=None,
        category="ADVANCED TOOLS",
    ),

    "K4": ToolDescription(
        key="K4",
        emoji="🚫",
        short_name="Blacklist",
        title="BLACKLIST MANAGEMENT",
        subtitle="Manage Domain Filter List",
        description=[
            "Add or remove domains from the blacklist. Blacklisted domains are",
            "automatically filtered from scrape results. Includes common platforms",
            "like Google, Facebook, LinkedIn, etc.",
        ],
        objectives=[
            "View current blacklist",
            "Add domains to blacklist",
            "Remove domains from blacklist",
            "Reset to defaults",
        ],
        next_step=None,
        category="ADVANCED TOOLS",
    ),

    "K5": ToolDescription(
        key="K5",
        emoji="🌐",
        short_name="Infra correlation",
        title="INFRASTRUCTURE CORRELATION",
        subtitle="Cross-Domain Analysis",
        description=[
            "Advanced analysis that correlates infrastructure across all scanned",
            "domains. Finds shared hosting, IP ranges, ASNs, and other technical",
            "indicators that might connect domains.",
        ],
        objectives=[
            "Shared IP addresses",
            "Same ASN/hosting provider",
            "Related SSL certificates",
            "Common DNS patterns",
            "Linked domain registrations",
        ],
        next_step="Note: Requires completed scans for analysis",
        category="ADVANCED TOOLS",
    ),

    "07": ToolDescription(
        key="07",
        emoji="⚙️",
        short_name="Configuration",
        title="CONFIGURATION",
        subtitle="Settings & Configuration",
        description=[
            "Modify PuppetMaster settings including keywords, scan parameters,",
            "output directories, and API keys.",
        ],
        objectives=[
            "Keywords for scraping",
            "SpiderFoot modules to enable",
            "Output directory paths",
            "Scan timeouts and limits",
            "API keys for services",
        ],
        next_step=None,
        category="SETTINGS",
    ),

    "08": ToolDescription(
        key="08",
        emoji="❓",
        short_name="Help & Documentation",
        title="HELP & DOCUMENTATION",
        subtitle="Full Tactical Manual",
        description=[
            "Complete guide to using PuppetMaster. Covers the entire workflow",
            "from discovery to analysis, with examples and best practices.",
        ],
        objectives=[
            "Quick start guide",
            "Full workflow walkthrough",
            "Understanding results",
            "Troubleshooting common issues",
            "Advanced techniques",
        ],
        next_step=None,
        category="SETTINGS",
    ),

    "09": ToolDescription(
        key="09",
        emoji="🖥️",
        short_name="Launch in tmux",
        title="TMUX SESSION",
        subtitle="Persistent Terminal Session",
        description=[
            "Launch PuppetMaster in a tmux session that survives SSH disconnects.",
            "Essential for long-running scans on remote servers. Reconnect anytime",
            "with 'tmux attach'.",
        ],
        objectives=[
            "Survives SSH disconnection",
            "Run scans overnight",
            "Reconnect from anywhere",
            "Multiple panes for monitoring",
        ],
        next_step="Command: tmux attach -t puppetmaster",
        category="SETTINGS",
    ),

    "10": ToolDescription(
        key="10",
        emoji="📊",
        short_name="System monitor (via Glances)",
        title="SYSTEM MONITOR",
        subtitle="Resource Usage via Glances",
        description=[
            "Launch Glances to monitor system resources during scans. Watch CPU,",
            "memory, disk space, and network usage in real-time.",
        ],
        objectives=[
            "CPU usage and load",
            "Memory consumption",
            "Disk space usage",
            "Network traffic",
            "Running processes",
        ],
        next_step=None,
        category="SETTINGS",
    ),

    "Q": ToolDescription(
        key="Q",
        emoji="👋",
        short_name="Quit",
        title="QUIT",
        subtitle="Exit PuppetMaster",
        description=[
            "Exit the PuppetMaster application. Any background scans will",
            "continue running if launched in the background.",
        ],
        objectives=[],
        next_step=None,
        category="QUIT",
    ),
}

def get_tool(key: str) -> Optional[ToolDescription]:
    """Get a tool description by key"""
    return TOOL_DESCRIPTIONS.get(key.upper())

def get_tools_by_category(category: str) -> List[ToolDescription]:
    """Get all tools in a category"""
    return [t for t in TOOL_DESCRIPTIONS.values() if t.category == category]

def get_categories() -> List[str]:
    """Get ordered list of categories"""
    return ["DISCOVERY & SCANNING", "ANALYSIS", "ADVANCED TOOLS", "SETTINGS"]

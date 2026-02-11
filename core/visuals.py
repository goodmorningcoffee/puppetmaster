"""
PUPPETMASTER Visual Styling Module

Dark cyberpunk aesthetic for consistent UI across all components.
"""

import re


# =============================================================================
# CYBERPUNK COLOR SCHEME
# =============================================================================

class C:
    """Dark cyberpunk color palette"""
    # Core colors
    BLACK = '\033[30m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'

    # Neon accents
    NEON_PINK = '\033[38;5;198m'
    NEON_CYAN = '\033[38;5;51m'
    NEON_GREEN = '\033[38;5;46m'
    NEON_ORANGE = '\033[38;5;208m'
    NEON_PURPLE = '\033[38;5;129m'
    NEON_RED = '\033[38;5;196m'

    # Dark tones
    DARK_GRAY = '\033[38;5;238m'
    MED_GRAY = '\033[38;5;244m'
    LIGHT_GRAY = '\033[38;5;250m'

    # Styles
    BOLD = '\033[1m'
    DIM = '\033[2m'
    ITALIC = '\033[3m'
    UNDERLINE = '\033[4m'
    BLINK = '\033[5m'
    REVERSE = '\033[7m'
    RESET = '\033[0m'

    # Background
    BG_BLACK = '\033[40m'
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_DARK = '\033[48;5;234m'


# =============================================================================
# BOX & FRAME DRAWING
# =============================================================================

def box(title: str, content: list, width: int = 60, accent: str = None) -> str:
    """
    Create a styled box with title and content.

    Args:
        title: Box title
        content: List of content lines
        width: Box width
        accent: Accent color (default: NEON_CYAN)

    Returns:
        Formatted box string
    """
    if accent is None:
        accent = C.NEON_CYAN

    lines = []
    lines.append(f"{accent}╔{'═' * (width-2)}╗{C.RESET}")

    # Title bar
    title_padded = f" {title} ".center(width-2)
    lines.append(f"{accent}║{C.RESET}{C.BOLD}{title_padded}{C.RESET}{accent}║{C.RESET}")
    lines.append(f"{accent}╠{'═' * (width-2)}╣{C.RESET}")

    # Content
    for line in content:
        clean = re.sub(r'\033\[[0-9;]*m', '', line)
        padding = width - 4 - len(clean)
        lines.append(f"{accent}║{C.RESET}  {line}{' ' * max(0, padding)}{accent}║{C.RESET}")

    lines.append(f"{accent}╚{'═' * (width-2)}╝{C.RESET}")
    return '\n'.join(lines)


def hline(char: str = '─', width: int = 60, color: str = None) -> str:
    """Horizontal line"""
    if color is None:
        color = C.DARK_GRAY
    return f"{color}{char * width}{C.RESET}"


def double_hline(width: int = 60, color: str = None) -> str:
    """Double horizontal line"""
    return hline('═', width, color or C.NEON_CYAN)


# =============================================================================
# MENU & PROMPT HELPERS
# =============================================================================

def menu_option(key: str, label: str, desc: str = "", active: bool = False) -> str:
    """
    Format a menu option.

    Args:
        key: Option key (e.g., '1', 'k1')
        label: Option label
        desc: Optional description
        active: Highlight as active/selected
    """
    if active:
        prefix = f"  {C.NEON_GREEN}▸ [{key}]{C.RESET}"
    else:
        prefix = f"  {C.NEON_CYAN}[{key}]{C.RESET}"

    if desc:
        return f"{prefix} {C.WHITE}{label}{C.RESET} {C.DARK_GRAY}// {desc}{C.RESET}"
    return f"{prefix} {C.WHITE}{label}{C.RESET}"


def prompt(text: str, color: str = None) -> str:
    """
    Styled input prompt.

    Args:
        text: Prompt text
        color: Prompt color (default: NEON_PINK)
    """
    if color is None:
        color = C.NEON_PINK
    return f"{color}>{C.RESET} {C.WHITE}{text}{C.RESET} "


def status(stype: str, msg: str) -> str:
    """
    Formatted status message.

    Args:
        stype: Status type (info, ok, warn, error, scan, data)
        msg: Status message
    """
    icons = {
        'info': f"{C.NEON_CYAN}[i]{C.RESET}",
        'ok': f"{C.NEON_GREEN}[✓]{C.RESET}",
        'success': f"{C.NEON_GREEN}[✓]{C.RESET}",
        'warn': f"{C.NEON_ORANGE}[!]{C.RESET}",
        'warning': f"{C.NEON_ORANGE}[!]{C.RESET}",
        'error': f"{C.NEON_RED}[✗]{C.RESET}",
        'fail': f"{C.NEON_RED}[✗]{C.RESET}",
        'scan': f"{C.NEON_PURPLE}[~]{C.RESET}",
        'data': f"{C.NEON_CYAN}[◆]{C.RESET}",
        'skip': f"{C.NEON_ORANGE}[−]{C.RESET}",
        'run': f"{C.NEON_CYAN}[▸]{C.RESET}",
    }
    icon = icons.get(stype, f"{C.WHITE}[*]{C.RESET}")
    return f"  {icon} {msg}"


def progress_dot(pstatus: str) -> str:
    """Get progress indicator for status"""
    indicators = {
        'starting': f"{C.NEON_PURPLE}●{C.RESET}",
        'running': f"{C.NEON_CYAN}○{C.RESET}",
        'scanning': f"{C.NEON_CYAN}○{C.RESET}",
        'complete': f"{C.NEON_GREEN}◆{C.RESET}",
        'success': f"{C.NEON_GREEN}◆{C.RESET}",
        'error': f"{C.NEON_RED}✗{C.RESET}",
        'skip': f"{C.NEON_ORANGE}−{C.RESET}",
        'correlating': f"{C.NEON_PINK}◇{C.RESET}",
    }
    return indicators.get(pstatus, f"{C.WHITE}○{C.RESET}")


# =============================================================================
# SECTION HEADERS
# =============================================================================

def section_header(title: str, width: int = 60, color: str = None) -> str:
    """
    Create a section header.

    Args:
        title: Section title
        width: Total width
        color: Accent color
    """
    if color is None:
        color = C.NEON_CYAN

    lines = []
    lines.append(f"{color}{'═' * width}{C.RESET}")
    lines.append(f"  {C.BOLD}{C.WHITE}{title}{C.RESET}")
    lines.append(f"{C.DARK_GRAY}{'─' * width}{C.RESET}")
    return '\n'.join(lines)


def subsection(title: str) -> str:
    """Simple subsection marker"""
    return f"  {C.NEON_CYAN}{title}{C.RESET}"


# =============================================================================
# DATA DISPLAY
# =============================================================================

def stat_line(label: str, value, highlight: bool = False) -> str:
    """
    Format a statistic line.

    Args:
        label: Stat label
        value: Stat value
        highlight: Highlight the value
    """
    if highlight:
        return f"    {label:20} {C.BOLD}{C.NEON_GREEN}{value}{C.RESET}"
    return f"    {label:20} {C.WHITE}{value}{C.RESET}"


def bar_chart(value: int, max_val: int = 20, color: str = None) -> str:
    """Simple horizontal bar"""
    if color is None:
        color = C.NEON_CYAN
    filled = min(value, max_val)
    return f"{color}{'█' * filled}{C.RESET}"


def domain_list(domains: list, max_show: int = 8, prefix: str = "│") -> list:
    """
    Format a list of domains for display.

    Returns list of formatted lines.
    """
    lines = []
    for d in domains[:max_show]:
        lines.append(f"  {C.NEON_CYAN}{prefix}{C.RESET} {d}")
    if len(domains) > max_show:
        lines.append(f"  {C.DARK_GRAY}{prefix} ... +{len(domains) - max_show} more{C.RESET}")
    return lines


# =============================================================================
# BANNERS
# =============================================================================

def mini_banner(tool_name: str, subtitle: str = "") -> str:
    """Create a mini banner for a tool"""
    lines = []
    lines.append(f"{C.NEON_CYAN}╔══════════════════════════════════════════╗{C.RESET}")
    title_line = f" {C.BOLD}{tool_name}{C.RESET} {C.DIM}// {subtitle}{C.RESET}"
    # Approximate padding (can't easily calculate with ANSI)
    lines.append(f"{C.NEON_CYAN}║{C.RESET}{title_line:42}{C.NEON_CYAN}║{C.RESET}")
    lines.append(f"{C.NEON_CYAN}╚══════════════════════════════════════════╝{C.RESET}")
    return '\n'.join(lines)


def result_banner(title: str, success: bool = True) -> str:
    """Create a result banner"""
    color = C.NEON_GREEN if success else C.NEON_RED
    lines = []
    lines.append(f"{color}╔{'═'*55}╗{C.RESET}")
    lines.append(f"{color}║{C.RESET} {C.BOLD}{title}{C.RESET}{' ' * (54 - len(title))}{color}║{C.RESET}")
    lines.append(f"{color}╚{'═'*55}╝{C.RESET}")
    return '\n'.join(lines)


# =============================================================================
# KALI-SPECIFIC STYLING
# =============================================================================

def kali_section_header() -> str:
    """Kali enhanced mode section header"""
    return f"""
{C.NEON_RED}╔══════════════════════════════════════════════════════════╗
║{C.RESET} {C.BOLD}{C.WHITE}KALI ENHANCED MODE{C.RESET}                                      {C.NEON_RED}║
╚══════════════════════════════════════════════════════════╝{C.RESET}"""


def scan_mode_indicator(mode_name: str, tools_available: int, tools_total: int) -> str:
    """Format scan mode indicator"""
    return f"  {C.DIM}Mode: {mode_name} | Tools: {tools_available}/{tools_total}{C.RESET}"


# =============================================================================
# CONFIRMATION & WARNING BOXES
# =============================================================================

def confirm_box(title: str, details: list, width: int = 55) -> str:
    """Orange confirmation box"""
    lines = []
    lines.append(f"{C.NEON_ORANGE}{'═' * width}{C.RESET}")
    lines.append(f"  {C.BOLD}{C.NEON_ORANGE}{title}{C.RESET}")
    lines.append(f"{C.DARK_GRAY}{'─' * width}{C.RESET}")
    for detail in details:
        lines.append(f"  {detail}")
    lines.append(f"{C.NEON_ORANGE}{'═' * width}{C.RESET}")
    return '\n'.join(lines)


def warning_text(msg: str) -> str:
    """Format warning text"""
    return f"{C.NEON_ORANGE}[!] {msg}{C.RESET}"


def error_text(msg: str) -> str:
    """Format error text"""
    return f"{C.NEON_RED}[✗] {msg}{C.RESET}"


def success_text(msg: str) -> str:
    """Format success text"""
    return f"{C.NEON_GREEN}[✓] {msg}{C.RESET}"


# =============================================================================
# QUICK FORMATTERS
# =============================================================================

def dim(text: str) -> str:
    """Dim text"""
    return f"{C.DIM}{text}{C.RESET}"


def bold(text: str) -> str:
    """Bold text"""
    return f"{C.BOLD}{text}{C.RESET}"


def cyan(text: str) -> str:
    """Cyan text"""
    return f"{C.NEON_CYAN}{text}{C.RESET}"


def green(text: str) -> str:
    """Green text"""
    return f"{C.NEON_GREEN}{text}{C.RESET}"


def orange(text: str) -> str:
    """Orange text"""
    return f"{C.NEON_ORANGE}{text}{C.RESET}"


def red(text: str) -> str:
    """Red text"""
    return f"{C.NEON_RED}{text}{C.RESET}"


def pink(text: str) -> str:
    """Pink text"""
    return f"{C.NEON_PINK}{text}{C.RESET}"


def purple(text: str) -> str:
    """Purple text"""
    return f"{C.NEON_PURPLE}{text}{C.RESET}"

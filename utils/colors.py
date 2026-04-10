"""
Canonical ANSI color definitions for PUPPETMASTER.

All modules should import colors from here to avoid duplication.
Convention: base names (RED, GREEN) use standard ANSI codes;
bright variants (BRIGHT_RED) use bright codes.
"""


class C:
    """ANSI color codes for terminal output"""

    # Styles
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    ITALIC = '\033[3m'
    UNDERLINE = '\033[4m'
    BLINK = '\033[5m'
    REVERSE = '\033[7m'

    # Standard colors
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'

    # Bright colors
    BRIGHT_BLACK = '\033[90m'
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'

    # Neon 256-color accents (from core/visuals.py cyberpunk theme)
    NEON_PINK = '\033[38;5;198m'
    NEON_CYAN = '\033[38;5;51m'
    NEON_GREEN = '\033[38;5;46m'
    NEON_ORANGE = '\033[38;5;208m'
    NEON_PURPLE = '\033[38;5;129m'
    NEON_RED = '\033[38;5;196m'

    # Grayscale tones
    DARK_GRAY = '\033[38;5;238m'
    MED_GRAY = '\033[38;5;244m'
    LIGHT_GRAY = '\033[38;5;250m'

    # Background colors
    BG_BLACK = '\033[40m'
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'
    BG_MAGENTA = '\033[45m'
    BG_CYAN = '\033[46m'
    BG_DARK = '\033[48;5;234m'


# Alias for upload.py which uses Colors.X instead of C.X
Colors = C

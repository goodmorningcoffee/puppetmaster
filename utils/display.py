#!/usr/bin/env python3
"""
display.py - Fun Terminal Display Utilities

Provides colorful output, animations, and progress indicators
to make the sock puppet hunting experience more enjoyable!
"""

import sys
import time
import random
import threading

# =============================================================================
# TERMINAL COLORS
# =============================================================================
from utils.colors import C

# =============================================================================
# FUN MESSAGES
# =============================================================================
HUNTING_MESSAGES = [
    "Hunting for sock puppets...",
    "Following the digital breadcrumbs...",
    "Unmasking the puppet show...",
    "Untangling the web of deception...",
    "Connecting the dots...",
    "Zeroing in on the puppet masters...",
    "Analyzing digital DNA...",
    "Mapping the shadow network...",
    "Illuminating hidden connections...",
    "Exposing the circus...",
]

COMPLETION_MESSAGES = [
    "Analysis complete! Time to expose some puppets!",
    "The puppet strings have been revealed!",
    "Mission accomplished! Check your results!",
    "Secrets uncovered! Review the findings!",
    "Bullseye! The network has been mapped!",
]

# =============================================================================
# SPINNER ANIMATIONS
# =============================================================================
SPINNERS = {
    'dots': ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'],
    'arrows': ['←', '↖', '↑', '↗', '→', '↘', '↓', '↙'],
    'bounce': ['⠁', '⠂', '⠄', '⠂'],
    'moon': ['🌑', '🌒', '🌓', '🌔', '🌕', '🌖', '🌗', '🌘'],
    'earth': ['🌍', '🌎', '🌏'],
    'clock': ['🕐', '🕑', '🕒', '🕓', '🕔', '🕕', '🕖', '🕗', '🕘', '🕙', '🕚', '🕛'],
    'runner': ['🏃', '🏃', '🏃💨', '🏃💨💨'],
    'detective': ['🕵️ ', '🕵️ 🔍', '🕵️ 🔍👀', '🕵️ 🔍'],
    'puppet': ['🎭', '🎪', '🎭', '🤹'],
    'spider': ['🕷️', '🕷️ ', '🕷️  ', '🕷️   '],
}

# =============================================================================
# PROGRESS BAR STYLES
# =============================================================================
PROGRESS_STYLES = [
    {'fill': '█', 'empty': '░', 'left': '│', 'right': '│', 'name': 'classic'},
    {'fill': '▓', 'empty': '░', 'left': '▐', 'right': '▌', 'name': 'blocks'},
    {'fill': '●', 'empty': '○', 'left': '(', 'right': ')', 'name': 'dots'},
    {'fill': '▰', 'empty': '▱', 'left': '▕', 'right': '▏', 'name': 'arrows'},
    {'fill': '━', 'empty': '─', 'left': '┃', 'right': '┃', 'name': 'lines'},
    {'fill': '⣿', 'empty': '⣀', 'left': '⎸', 'right': '⎹', 'name': 'braille'},
    {'fill': '🟩', 'empty': '⬜', 'left': '', 'right': '', 'name': 'squares'},
    {'fill': '🔥', 'empty': '⬜', 'left': '', 'right': '', 'name': 'fire'},
    {'fill': '🐍', 'empty': '·', 'left': '', 'right': '', 'name': 'snake'},
]

# =============================================================================
# ASCII LOADING ANIMATIONS
# =============================================================================
LOADING_ANIMATIONS = {
    'wave': [
        "≋≈≋≈≋",
        "≈≋≈≋≈",
    ],
    'fish': [
        "><>        ",
        " ><>       ",
        "  ><>      ",
        "   ><>     ",
        "    ><>    ",
        "     ><>   ",
        "      ><>  ",
        "       ><> ",
        "        ><>",
        "       ><> ",
        "      ><>  ",
        "     ><>   ",
        "    ><>    ",
        "   ><>     ",
        "  ><>      ",
        " ><>       ",
    ],
    'worm': [
        "🐛·····",
        "·🐛····",
        "··🐛···",
        "···🐛··",
        "····🐛·",
        "·····🐛",
        "····🐛·",
        "···🐛··",
        "··🐛···",
        "·🐛····",
    ],
    'snake': [
        "🐍▪▪▪▪",
        "▪🐍▪▪▪",
        "▪▪🐍▪▪",
        "▪▪▪🐍▪",
        "▪▪▪▪🐍",
    ],
    'spider': [
        "🕷️ ···",
        "·🕷️ ··",
        "··🕷️ ·",
        "···🕷️ ",
        "··🕷️ ·",
        "·🕷️ ··",
    ],
    'puppet': [
        "🎭    ",
        " 🎭   ",
        "  🎭  ",
        "   🎭 ",
        "    🎭",
        "   🎭 ",
        "  🎭  ",
        " 🎭   ",
    ],
}

# =============================================================================
# STAGE ICONS AND COLORS
# =============================================================================
STAGE_COLORS = [
    C.BRIGHT_CYAN,
    C.BRIGHT_MAGENTA,
    C.BRIGHT_YELLOW,
    C.BRIGHT_GREEN,
    C.BRIGHT_BLUE,
    C.BRIGHT_RED,
]

STAGE_ICONS = ['📥', '🔬', '🕸️', '🔍', '🎯', '📝']

# =============================================================================
# ANSI ESCAPE CODES FOR CURSOR CONTROL
# =============================================================================
CURSOR_UP = "\033[A"      # Move cursor up one line
CURSOR_DOWN = "\033[B"    # Move cursor down one line
CURSOR_SAVE = "\033[s"    # Save cursor position
CURSOR_RESTORE = "\033[u" # Restore cursor position
CLEAR_LINE = "\033[K"     # Clear from cursor to end of line
CURSOR_START = "\r"       # Carriage return (start of line)


# =============================================================================
# FUN SPINNER CLASS
# =============================================================================
class FunSpinner:
    """
    Animated spinner for long operations.

    Can run in two modes:
    - Single-line mode (default): Spinner overwrites current line
    - Multi-line mode (above_progress=True): Spinner on line above, leaves room for tqdm below
    """

    def __init__(self, message="Processing", style='dots', color=C.BRIGHT_CYAN, above_progress=False):
        self.message = message
        self.frames = SPINNERS.get(style, SPINNERS['dots'])
        self.color = color
        self.running = False
        self.thread = None
        self.frame_idx = 0
        self.above_progress = above_progress  # If True, animate on line above tqdm

    def _spin_single_line(self):
        """Original single-line spinner behavior"""
        while self.running:
            frame = self.frames[self.frame_idx % len(self.frames)]
            print(f"\r{self.color}{frame}{C.RESET} {self.message}{CLEAR_LINE}", end='', flush=True)
            self.frame_idx += 1
            time.sleep(0.1)

    def _spin_above_progress(self):
        """
        Spinner that animates on the line ABOVE the current position.
        This allows tqdm to run on the line below without interference.

        Layout:
          Line N-1: 🕵️ 🔍 Analyzing...  <- spinner updates here
          Line N:   ████░░░░ 50%        <- tqdm updates here (current cursor position)
        """
        while self.running:
            frame = self.frames[self.frame_idx % len(self.frames)]
            # Save position, move up, print spinner, clear rest of line, restore position
            output = f"{CURSOR_SAVE}{CURSOR_UP}{CURSOR_START}{self.color}{frame}{C.RESET} {self.message}{CLEAR_LINE}{CURSOR_RESTORE}"
            print(output, end='', flush=True)
            self.frame_idx += 1
            time.sleep(0.1)

    def start(self):
        """Start the spinner animation in a background thread"""
        self.running = True

        if self.above_progress:
            # Print a blank line first to reserve space for spinner above
            print()  # This becomes the tqdm line
            # Now cursor is on tqdm line, spinner will animate on line above
            target = self._spin_above_progress
        else:
            target = self._spin_single_line

        self.thread = threading.Thread(target=target)
        self.thread.daemon = True
        self.thread.start()

    def stop(self, final_message=None):
        """Stop the spinner and show completion message"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=0.5)

        msg = final_message or f"{self.message} - Done!"

        if self.above_progress:
            # Update the spinner line (above) with completion message
            output = f"{CURSOR_SAVE}{CURSOR_UP}{CURSOR_START}{C.GREEN}✓{C.RESET} {msg}{CLEAR_LINE}{CURSOR_RESTORE}"
            print(output, end='', flush=True)
        else:
            print(f"\r{C.GREEN}✓{C.RESET} {msg}{CLEAR_LINE}")

    def update_message(self, new_message):
        """Update the spinner message while it's running"""
        self.message = new_message

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.stop(f"{self.message} - Failed!")
        else:
            self.stop()
        return False


# =============================================================================
# PROGRESS BAR FUNCTIONS
# =============================================================================
def fun_progress_bar(current, total, width=30, style_idx=None):
    """Generate a fun progress bar string"""
    if style_idx is None:
        style_idx = random.randint(0, len(PROGRESS_STYLES) - 1)
    style = PROGRESS_STYLES[style_idx % len(PROGRESS_STYLES)]

    percent = current / total if total > 0 else 0
    filled = int(width * percent)
    empty = width - filled

    bar = style['left'] + style['fill'] * filled + style['empty'] * empty + style['right']
    percent_str = f"{percent * 100:5.1f}%"

    return f"{bar} {percent_str}"


def print_progress(current, total, message="", width=30, style_idx=None):
    """Print an updating progress bar"""
    bar = fun_progress_bar(current, total, width, style_idx)
    print(f"\r{bar} {message}", end='', flush=True)
    if current >= total:
        print()  # Newline when complete


# =============================================================================
# ANIMATED LOADING FUNCTIONS
# =============================================================================
def animated_loading(message, duration=2, animation='fish'):
    """Show an animated loading sequence for a set duration"""
    frames = LOADING_ANIMATIONS.get(animation, LOADING_ANIMATIONS['fish'])
    end_time = time.time() + duration
    frame_idx = 0

    while time.time() < end_time:
        frame = frames[frame_idx % len(frames)]
        print(f"\r{C.BRIGHT_CYAN}{frame}{C.RESET} {message}", end='', flush=True)
        frame_idx += 1
        time.sleep(0.15)
    print(f"\r{C.GREEN}✓{C.RESET} {message} - Complete!" + " " * 20)


# =============================================================================
# STAGE HEADERS
# =============================================================================
def print_stage_header(stage_num, total_stages, title, icon=None):
    """Print a colorful stage header"""
    color = STAGE_COLORS[(stage_num - 1) % len(STAGE_COLORS)]
    if icon is None:
        icon = STAGE_ICONS[(stage_num - 1) % len(STAGE_ICONS)]

    print()
    print(f"{color}{'─' * 60}{C.RESET}")
    print(f"{color}  {icon} Stage {stage_num}/{total_stages}: {C.BOLD}{title}{C.RESET}")
    print(f"{color}{'─' * 60}{C.RESET}")


def print_stage_complete(stage_num, total_stages, title, stats=None):
    """Print a stage completion message with optional stats"""
    color = STAGE_COLORS[(stage_num - 1) % len(STAGE_COLORS)]
    print(f"{color}  ✓ {title} complete!{C.RESET}", end='')
    if stats:
        print(f" {C.DIM}({stats}){C.RESET}")
    else:
        print()


# =============================================================================
# SECTION DIVIDERS
# =============================================================================
def print_section(title, color=None):
    """Print a section header"""
    if color is None:
        color = C.BRIGHT_CYAN
    print(f"\n{color}{'═' * 60}{C.RESET}")
    print(f"{color}  {title}{C.RESET}")
    print(f"{color}{'═' * 60}{C.RESET}")


def print_subsection(title, color=None):
    """Print a subsection header"""
    if color is None:
        color = C.CYAN
    print(f"\n{color}{'─' * 50}{C.RESET}")
    print(f"{color}  {title}{C.RESET}")
    print(f"{color}{'─' * 50}{C.RESET}")


# =============================================================================
# STATUS MESSAGES
# =============================================================================
def print_info(message):
    """Print an info message"""
    print(f"{C.BRIGHT_BLUE}ℹ{C.RESET} {message}")


def print_success(message):
    """Print a success message"""
    print(f"{C.BRIGHT_GREEN}✓{C.RESET} {message}")


def print_warning(message):
    """Print a warning message"""
    print(f"{C.BRIGHT_YELLOW}⚠{C.RESET} {message}")


def print_error(message):
    """Print an error message"""
    print(f"{C.BRIGHT_RED}✗{C.RESET} {message}")


# =============================================================================
# ANIMATED TEXT
# =============================================================================
def animated_print(text, delay=0.02, color=None):
    """Print text with a typewriter effect"""
    if color:
        print(color, end='')
    for char in text:
        print(char, end='', flush=True)
        time.sleep(delay)
    if color:
        print(C.RESET, end='')
    print()


def random_hunting_message():
    """Get a random hunting message"""
    return random.choice(HUNTING_MESSAGES)


def random_completion_message():
    """Get a random completion message"""
    return random.choice(COMPLETION_MESSAGES)


# =============================================================================
# CELEBRATION ANIMATIONS
# =============================================================================
def celebrate(message="Analysis Complete!"):
    """Show a celebration animation"""
    frames = [
        "🎉",
        "🎉✨",
        "🎉✨🎊",
        "🎉✨🎊🎆",
        "🎉✨🎊🎆🎇",
    ]
    for frame in frames:
        print(f"\r{frame} {C.BRIGHT_GREEN}{message}{C.RESET}", end='', flush=True)
        time.sleep(0.2)
    print()

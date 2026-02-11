"""
Kali Tool Wrappers

Provides unified Python interfaces for Kali Linux security tools.
Each wrapper normalizes output to a common format for pipeline integration.

Tools are organized by phase:
- Discovery: theHarvester, amass, sublist3r, fierce
- Scanning: whatweb, wafw00f, sslscan, nmap, nikto, dnsrecon, dnsenum
- Analysis: metagoofil, exiftool
- Cross: dmitry, sherlock
"""

from .base import BaseTool, ToolResult, ToolError
from .theharvester import TheHarvester
from .amass import Amass
from .sublist3r import Sublist3r
from .fierce import Fierce
from .whatweb import WhatWeb
from .wafw00f import Wafw00f
from .sslscan import SSLScan
from .nmap import Nmap
from .nikto import Nikto
from .dnsrecon import DNSRecon
from .dnsenum import DNSEnum
from .metagoofil import Metagoofil
from .exiftool import ExifTool
from .dmitry import DMitry
from .sherlock import Sherlock

# Tool registry for easy access
TOOL_CLASSES = {
    'theHarvester': TheHarvester,
    'amass': Amass,
    'sublist3r': Sublist3r,
    'fierce': Fierce,
    'whatweb': WhatWeb,
    'wafw00f': Wafw00f,
    'sslscan': SSLScan,
    'nmap': Nmap,
    'nikto': Nikto,
    'dnsrecon': DNSRecon,
    'dnsenum': DNSEnum,
    'metagoofil': Metagoofil,
    'exiftool': ExifTool,
    'dmitry': DMitry,
    'sherlock': Sherlock,
}


def get_tool(name: str) -> BaseTool:
    """Get a tool wrapper instance by name"""
    if name not in TOOL_CLASSES:
        raise ValueError(f"Unknown tool: {name}")
    return TOOL_CLASSES[name]()


__all__ = [
    'BaseTool',
    'ToolResult',
    'ToolError',
    'get_tool',
    'TOOL_CLASSES',
    'TheHarvester',
    'Amass',
    'Sublist3r',
    'Fierce',
    'WhatWeb',
    'Wafw00f',
    'SSLScan',
    'Nmap',
    'Nikto',
    'DNSRecon',
    'DNSEnum',
    'Metagoofil',
    'ExifTool',
    'DMitry',
    'Sherlock',
]

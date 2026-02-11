"""
Discovery Aggregator Module

Runs all discovery tools based on the selected mode and aggregates
results into a single deduplicated domains.txt file.

This is the main entry point for the enhanced discovery phase.
"""

import os
import time
import concurrent.futures
from dataclasses import dataclass, field
from typing import List, Set, Dict, Optional, Callable
from datetime import datetime
from pathlib import Path

from .modes import ScanMode, get_mode_config, ModeConfig
from .registry import get_registry, ToolInfo
from .tools.base import ToolResult, ToolError


@dataclass
class AggregatedResult:
    """Combined results from all discovery tools"""
    mode: ScanMode
    target: str                             # Original target/seed domain
    timestamp: str

    # Aggregated domains
    domains: Set[str] = field(default_factory=set)
    subdomains: Set[str] = field(default_factory=set)
    emails: Set[str] = field(default_factory=set)
    ips: Set[str] = field(default_factory=set)

    # Per-tool results
    tool_results: Dict[str, ToolResult] = field(default_factory=dict)

    # Statistics
    tools_run: int = 0
    tools_succeeded: int = 0
    tools_failed: int = 0
    errors: List[str] = field(default_factory=list)

    def total_domains(self) -> int:
        """Total unique domains found"""
        return len(self.domains) + len(self.subdomains)

    def to_domains_list(self) -> List[str]:
        """Get sorted list of all domains"""
        all_domains = self.domains | self.subdomains
        return sorted(all_domains)


class DiscoveryAggregator:
    """
    Orchestrates running multiple discovery tools and aggregating results.

    Usage:
        aggregator = DiscoveryAggregator(mode=ScanMode.STANDARD)
        result = aggregator.run('target-domain.com')
        aggregator.save_domains(result, 'domains.txt')
    """

    def __init__(self, mode: ScanMode = ScanMode.STANDARD,
                 parallel: bool = True, max_workers: int = 3,
                 progress_callback: Optional[Callable] = None):
        """
        Initialize aggregator.

        Args:
            mode: Scan mode (Ghost/Stealth/Standard/Deep)
            parallel: Run tools in parallel
            max_workers: Max concurrent tools
            progress_callback: Optional callback(tool_name, status, message)
        """
        self.mode = mode
        self.parallel = parallel
        self.max_workers = max_workers
        self.progress_callback = progress_callback
        self.registry = get_registry()

    def _report_progress(self, tool: str, status: str, message: str = ""):
        """Report progress to callback"""
        if self.progress_callback:
            self.progress_callback(tool, status, message)

    def _run_tool(self, tool_cmd: str, target: str, passive: bool = False) -> Optional[ToolResult]:
        """Run a single tool and return result"""
        from .tools import get_tool

        self._report_progress(tool_cmd, "running", f"Starting {tool_cmd}...")

        try:
            tool = get_tool(tool_cmd)

            if passive and hasattr(tool, 'run_passive'):
                result = tool.run_passive(target)
            else:
                result = tool.run(target)

            self._report_progress(tool_cmd, "success",
                                  f"Found {len(result.subdomains)} subdomains, {len(result.emails)} emails")
            return result

        except ToolError as e:
            self._report_progress(tool_cmd, "error", str(e))
            return None
        except Exception as e:
            self._report_progress(tool_cmd, "error", f"Unexpected error: {e}")
            return None

    def run(self, target: str) -> AggregatedResult:
        """
        Run all discovery tools for the selected mode.

        Args:
            target: Target domain to investigate

        Returns:
            AggregatedResult with combined findings
        """
        config = get_mode_config(self.mode)

        result = AggregatedResult(
            mode=self.mode,
            target=target,
            timestamp=datetime.now().isoformat()
        )

        # Get discovery tools for this mode
        discovery_tools = config.tools.get('discovery', [])

        # Filter to only available tools
        available_tools = [t for t in discovery_tools if self.registry.is_available(t)]

        if not available_tools:
            result.errors.append("No discovery tools available for this mode")
            return result

        self._report_progress("aggregator", "starting",
                              f"Running {len(available_tools)} discovery tools in {self.mode.value} mode")

        # Determine if we should use passive mode
        passive = self.mode in [ScanMode.GHOST, ScanMode.STEALTH]

        if self.parallel and len(available_tools) > 1:
            # Run tools in parallel
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(self._run_tool, tool, target, passive): tool
                    for tool in available_tools
                }

                for future in concurrent.futures.as_completed(futures):
                    tool_name = futures[future]
                    result.tools_run += 1

                    try:
                        tool_result = future.result()
                        if tool_result:
                            result.tool_results[tool_name] = tool_result
                            result.tools_succeeded += 1

                            # Merge results
                            result.domains.update(tool_result.domains)
                            result.subdomains.update(tool_result.subdomains)
                            result.emails.update(tool_result.emails)
                            result.ips.update(tool_result.ips)
                        else:
                            result.tools_failed += 1
                    except Exception as e:
                        result.tools_failed += 1
                        result.errors.append(f"{tool_name}: {str(e)}")
        else:
            # Run tools sequentially
            for tool_name in available_tools:
                result.tools_run += 1

                tool_result = self._run_tool(tool_name, target, passive)

                if tool_result:
                    result.tool_results[tool_name] = tool_result
                    result.tools_succeeded += 1

                    # Merge results
                    result.domains.update(tool_result.domains)
                    result.subdomains.update(tool_result.subdomains)
                    result.emails.update(tool_result.emails)
                    result.ips.update(tool_result.ips)
                else:
                    result.tools_failed += 1

        self._report_progress("aggregator", "complete",
                              f"Found {result.total_domains()} unique domains")

        return result

    def save_domains(self, result: AggregatedResult, output_path: str,
                     include_seed: bool = True) -> int:
        """
        Save discovered domains to a text file.

        Args:
            result: Aggregated results
            output_path: Path to output file
            include_seed: Include the original target domain

        Returns:
            Number of domains written
        """
        domains = result.to_domains_list()

        # Optionally include seed domain
        if include_seed and result.target not in domains:
            domains.insert(0, result.target)

        # Deduplicate and sort
        domains = sorted(set(domains))

        # Write to file
        with open(output_path, 'w') as f:
            for domain in domains:
                f.write(domain + '\n')

        return len(domains)

    def save_full_report(self, result: AggregatedResult, output_dir: str) -> Dict[str, str]:
        """
        Save full report including all discovered data.

        Args:
            result: Aggregated results
            output_dir: Output directory

        Returns:
            Dict of output file paths
        """
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        files = {}

        # Domains list
        domains_file = os.path.join(output_dir, f'domains_{timestamp}.txt')
        self.save_domains(result, domains_file)
        files['domains'] = domains_file

        # Emails list
        if result.emails:
            emails_file = os.path.join(output_dir, f'emails_{timestamp}.txt')
            with open(emails_file, 'w') as f:
                for email in sorted(result.emails):
                    f.write(email + '\n')
            files['emails'] = emails_file

        # IPs list
        if result.ips:
            ips_file = os.path.join(output_dir, f'ips_{timestamp}.txt')
            with open(ips_file, 'w') as f:
                for ip in sorted(result.ips):
                    f.write(ip + '\n')
            files['ips'] = ips_file

        # Summary report
        summary_file = os.path.join(output_dir, f'discovery_summary_{timestamp}.md')
        with open(summary_file, 'w') as f:
            f.write(f"# Discovery Report\n\n")
            f.write(f"**Target:** {result.target}\n")
            f.write(f"**Mode:** {result.mode.value}\n")
            f.write(f"**Timestamp:** {result.timestamp}\n\n")
            f.write(f"## Statistics\n\n")
            f.write(f"- Tools Run: {result.tools_run}\n")
            f.write(f"- Tools Succeeded: {result.tools_succeeded}\n")
            f.write(f"- Tools Failed: {result.tools_failed}\n")
            f.write(f"- Domains Found: {len(result.domains)}\n")
            f.write(f"- Subdomains Found: {len(result.subdomains)}\n")
            f.write(f"- Emails Found: {len(result.emails)}\n")
            f.write(f"- IPs Found: {len(result.ips)}\n\n")

            if result.errors:
                f.write(f"## Errors\n\n")
                for error in result.errors:
                    f.write(f"- {error}\n")

        files['summary'] = summary_file

        return files


def run_discovery(target: str, mode: ScanMode = ScanMode.STANDARD,
                  output_file: str = None,
                  progress_callback: Callable = None) -> AggregatedResult:
    """
    Convenience function to run discovery and save results.

    Args:
        target: Target domain
        mode: Scan mode
        output_file: Optional output file path
        progress_callback: Optional progress callback

    Returns:
        AggregatedResult
    """
    aggregator = DiscoveryAggregator(
        mode=mode,
        progress_callback=progress_callback
    )

    result = aggregator.run(target)

    if output_file:
        aggregator.save_domains(result, output_file)

    return result


# Quick test
if __name__ == '__main__':
    def print_progress(tool, status, message):
        print(f"[{status.upper():8}] {tool}: {message}")

    print("Testing Discovery Aggregator")
    print("=" * 50)

    aggregator = DiscoveryAggregator(
        mode=ScanMode.GHOST,
        progress_callback=print_progress
    )

    # Just show what tools would run
    config = get_mode_config(ScanMode.GHOST)
    print(f"\nMode: {config.name}")
    print(f"Discovery tools: {config.tools.get('discovery', [])}")

    registry = get_registry()
    available = [t for t in config.tools.get('discovery', []) if registry.is_available(t)]
    print(f"Available tools: {available}")

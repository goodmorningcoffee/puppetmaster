"""
kali_adapter.py - Bridge between Kali infrastructure analyzer and main pipeline.

The Kali infrastructure analyzer (kali/infra_analyzer.py) produces
`InfraCorrelation` objects with float weights (0.0-1.0) describing how
strongly two or more domains are correlated by shared infrastructure
(SSL certs, IPs, nameservers, document metadata, social usernames).

The main analysis pipeline uses `Signal` objects with tier enums
(SMOKING_GUN, STRONG, WEAK). These two systems were developed
independently and never spoke the same language — meaning Kali findings
showed up only in the separate `./infra_analysis/` report and never
made it into the main `executive_summary.md`.

This module bridges the two by converting `InfraCorrelation` objects (or
their JSON-serialized form) into `Signal` objects with appropriate tiers.

Tier mapping:
    weight >= 0.95  ->  SMOKING_GUN
    weight >= 0.60  ->  STRONG
    weight <  0.60  ->  WEAK

Concrete mapping for the existing Kali correlation types:
    SMOKING_GUN:
        shared_ssl_fingerprint  (1.0)  - same exact SSL cert
        shared_email            (0.95) - same contact email
        shared_social_username  (0.95) - same username on social platforms
    STRONG:
        shared_ip               (0.9)  - same IP address
        shared_author           (0.9)  - same document author in metadata
        shared_ssl_org          (0.85) - same org in SSL cert
        shared_mx               (0.8)  - same mail server
        shared_nameserver       (0.7)  - same NS records
        shared_email_domain     (0.7)  - emails from same custom domain
        shared_ip_range         (0.6)  - same /24 subnet
    WEAK:
        shared_tech_stack       (0.5)  - same CMS/framework combo
        shared_server_signature (0.4)  - same web server signature
        shared_ssl_issuer       (0.3)  - same SSL issuer (Let's Encrypt etc.)
        shared_creator_tool     (0.3)  - same document creation tool

Signal type prefix:
    All converted signals use `kali_<original_name>` so they don't collide
    with the main detector signal types. Example: a Kali `shared_ip`
    correlation becomes a Signal with `signal_type='kali_shared_ip'`,
    distinct from the `ip_address` signal from IPAddressDetector.

    This means the same underlying fact (e.g., two domains sharing an IP)
    might produce both a `kali_shared_ip` AND an `ip_address` signal in
    the merged output. That's intentional — each is an independent piece
    of evidence and the graph builder weights them accordingly.
"""

import glob
import json
import os
from typing import List, Optional

from .signals import Signal, SignalTier


# Tier thresholds — see module docstring for the rationale
SMOKING_GUN_THRESHOLD = 0.95
STRONG_THRESHOLD = 0.60


def weight_to_tier(weight: float) -> SignalTier:
    """Map a Kali correlation float weight to a Signal tier."""
    if weight >= SMOKING_GUN_THRESHOLD:
        return SignalTier.SMOKING_GUN
    if weight >= STRONG_THRESHOLD:
        return SignalTier.STRONG
    return SignalTier.WEAK


def correlation_to_signal(corr) -> Signal:
    """
    Convert one Kali InfraCorrelation object to a Signal.

    Args:
        corr: A kali.infra_analyzer.InfraCorrelation instance, OR a dict
              with the same field names (as produced by the JSON serializer).

    Returns:
        A Signal object suitable for merging into the main pipeline output.
    """
    # Support both InfraCorrelation objects and dict shape (from JSON)
    if isinstance(corr, dict):
        signal_type = corr.get("signal_type", "unknown")
        weight = float(corr.get("weight", 0.0))
        domains = set(corr.get("domains", []))
        shared_value = str(corr.get("shared_value", ""))
        description = corr.get("description", "")
    else:
        signal_type = getattr(corr, "signal_type", "unknown")
        weight = float(getattr(corr, "weight", 0.0))
        domains = set(getattr(corr, "domains", []))
        shared_value = str(getattr(corr, "shared_value", ""))
        description = getattr(corr, "description", "")

    return Signal(
        tier=weight_to_tier(weight),
        signal_type=f"kali_{signal_type}",
        value=shared_value,
        domains=domains,
        source_module="kali_infra_analyzer",
        description=f"[Kali] {description}",
    )


def correlations_to_signals(correlations) -> List[Signal]:
    """
    Convert a list of Kali correlations to a list of Signal objects.

    Args:
        correlations: List of InfraCorrelation objects or dicts.

    Returns:
        List of Signal objects (one per correlation).
    """
    return [correlation_to_signal(c) for c in correlations]


def load_latest_infra_analysis(infra_dir: str) -> Optional[dict]:
    """
    Load the most recent `infrastructure_*.json` file from a Kali infra
    analysis output directory.

    The Kali analyzer saves results as `infrastructure_<timestamp>.json`
    in the output directory it's pointed at. This function finds the most
    recent such file and returns its parsed JSON content.

    Args:
        infra_dir: Path to a Kali infra analysis output directory.

    Returns:
        Parsed JSON dict, or None if no infrastructure_*.json files exist
        or if the directory doesn't exist.
    """
    if not os.path.isdir(infra_dir):
        return None

    pattern = os.path.join(infra_dir, "infrastructure_*.json")
    matches = glob.glob(pattern)
    if not matches:
        return None

    # Sort by mtime descending — most recent first
    matches.sort(key=os.path.getmtime, reverse=True)
    latest = matches[0]

    try:
        with open(latest) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def load_infra_signals(infra_dir: str) -> List[Signal]:
    """
    Load Kali infra analysis from a directory and return Signal objects.

    Convenience function that combines `load_latest_infra_analysis()` and
    `correlations_to_signals()`. Intended for use from `run_full_pipeline()`
    to merge Kali findings into the main signal pile.

    Args:
        infra_dir: Path to a Kali infra analysis output directory.

    Returns:
        List of Signal objects (empty if no infra analysis found).
    """
    data = load_latest_infra_analysis(infra_dir)
    if data is None:
        return []

    correlations = data.get("correlations", [])
    return correlations_to_signals(correlations)


def merge_kali_signals_into(all_signals: dict, kali_signals: List[Signal]) -> int:
    """
    Merge a list of Kali Signal objects into the main signal dict in-place.

    Uses the same `(signal_type, value)` keying as `extract_all_signals()`
    so that if the same Kali signal is loaded twice, the domains get
    merged rather than duplicated.

    Args:
        all_signals: The dict returned/built by SignalExtractor.extract_all_signals.
                     Modified in place.
        kali_signals: Signals to merge in.

    Returns:
        Number of new signal entries added (existing entries get domain merge,
        not counted as "new").
    """
    new_count = 0
    for sig in kali_signals:
        key = (sig.signal_type, sig.value)
        if key in all_signals:
            all_signals[key].domains.update(sig.domains)
        else:
            all_signals[key] = sig
            new_count += 1
    return new_count

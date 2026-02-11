#!/usr/bin/env python3
"""
spiderfoot_api.py - HTTP API Client for SpiderFoot Web Server

Provides programmatic access to SpiderFoot running in web server mode.
This bypasses SQLite lock contention by using the web server's internal
concurrency management instead of spawning separate CLI processes.

Usage:
    api = SpiderFootAPI("worker-host.example.com", port=5001)
    scan_id = api.start_scan("example.com", usecase="all")
    status = api.get_status(scan_id)
    csv_data = api.get_results_csv(scan_id)
"""

import time
import urllib.parse
from dataclasses import dataclass
from typing import Optional, Dict, List, Any, Tuple
from enum import Enum

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class ScanStatus(Enum):
    """SpiderFoot scan status values."""
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    FINISHED = "FINISHED"
    ABORTED = "ABORTED"
    ERROR = "ERROR-FAILED"
    UNKNOWN = "UNKNOWN"


@dataclass
class ScanInfo:
    """Information about a SpiderFoot scan."""
    scan_id: str
    name: str
    target: str
    status: ScanStatus
    created: Optional[str] = None
    started: Optional[str] = None
    ended: Optional[str] = None

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> 'ScanInfo':
        """Create ScanInfo from API response."""
        status_str = data.get('status', 'UNKNOWN')
        try:
            status = ScanStatus(status_str)
        except ValueError:
            status = ScanStatus.UNKNOWN

        return cls(
            scan_id=data.get('id', ''),
            name=data.get('name', ''),
            target=data.get('target', ''),
            status=status,
            created=data.get('created'),
            started=data.get('started'),
            ended=data.get('ended'),
        )


class SpiderFootAPIError(Exception):
    """Exception raised for SpiderFoot API errors."""
    pass


class SpiderFootAPI:
    """
    HTTP client for SpiderFoot web API.

    Communicates with a SpiderFoot instance running in web server mode
    (started with `sf.py -l 0.0.0.0:5001`).

    Attributes:
        host: Hostname or IP of the SpiderFoot web server
        port: Port number (default 5001)
        timeout: Request timeout in seconds
    """

    DEFAULT_PORT = 5001
    DEFAULT_TIMEOUT = 30

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_PORT,
        timeout: int = DEFAULT_TIMEOUT
    ):
        """
        Initialize SpiderFoot API client.

        Args:
            host: Hostname or IP of the worker running SpiderFoot
            port: Web server port (default 5001)
            timeout: HTTP request timeout in seconds
        """
        if not REQUESTS_AVAILABLE:
            raise ImportError(
                "requests library required for SpiderFootAPI. "
                "Install with: pip install requests"
            )

        self.host = host
        self.port = port
        self.timeout = timeout
        self.base_url = f"http://{host}:{port}"
        self._session = requests.Session()

    def _get(self, endpoint: str, params: Optional[Dict] = None) -> requests.Response:
        """Make GET request to SpiderFoot API."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            response = self._session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            raise SpiderFootAPIError(f"GET {endpoint} failed: {e}")

    def _post(self, endpoint: str, data: Optional[Dict] = None) -> requests.Response:
        """Make POST request to SpiderFoot API."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            response = self._session.post(url, data=data, timeout=self.timeout)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            raise SpiderFootAPIError(f"POST {endpoint} failed: {e}")

    def is_alive(self) -> bool:
        """
        Check if the SpiderFoot web server is responding.

        Returns:
            True if server is responding, False otherwise
        """
        try:
            response = self._session.get(
                f"{self.base_url}/",
                timeout=5
            )
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def wait_for_ready(self, max_wait: int = 60, poll_interval: int = 2) -> bool:
        """
        Wait for the SpiderFoot web server to become ready.

        Args:
            max_wait: Maximum seconds to wait
            poll_interval: Seconds between checks

        Returns:
            True if server became ready, False if timeout
        """
        start = time.time()
        while time.time() - start < max_wait:
            if self.is_alive():
                return True
            time.sleep(poll_interval)
        return False

    def start_scan(
        self,
        target: str,
        name: Optional[str] = None,
        usecase: str = "all",
        modules: Optional[List[str]] = None,
        types: Optional[List[str]] = None
    ) -> str:
        """
        Start a new scan on the SpiderFoot server.

        Args:
            target: Target to scan (domain, IP, email, etc.)
            name: Scan name (defaults to target if not specified)
            usecase: Module preset - "all", "footprint", "investigate", "passive"
            modules: Optional list of specific modules to enable
            types: Optional list of event types to collect

        Returns:
            Scan ID string

        Raises:
            SpiderFootAPIError: If scan creation fails
        """
        if name is None:
            name = f"scan_{target}_{int(time.time())}"

        # Build form data for startscan endpoint
        data = {
            'scanname': name,
            'scantarget': target,
            'usecase': usecase,
        }

        if modules:
            # SpiderFoot expects module names prefixed with "module_"
            data['modulelist'] = ','.join(f"module_{m}" for m in modules)

        if types:
            # SpiderFoot expects type names prefixed with "type_"
            data['typelist'] = ','.join(f"type_{t}" for t in types)

        try:
            response = self._post('/startscan', data=data)

            # The startscan endpoint returns HTML with scan info
            # We need to extract the scan ID from the response
            # Look for scan ID in the response (format varies by version)
            content = response.text

            # Try to find scan ID in the response
            # SpiderFoot returns HTML that contains the scan ID
            # Common patterns: scanId=xxx or id=xxx in URL, or JSON response

            # Try JSON response first (some versions)
            try:
                json_data = response.json()
                if 'scanId' in json_data:
                    return json_data['scanId']
                if 'id' in json_data:
                    return json_data['id']
            except ValueError:
                pass

            # Look for scan ID in HTML/redirect URL
            import re

            # Pattern 1: scaninfo?id=XXX in redirect or link
            match = re.search(r'scaninfo\?id=([a-zA-Z0-9-]+)', content)
            if match:
                return match.group(1)

            # Pattern 2: data-id="XXX"
            match = re.search(r'data-id=["\']([a-zA-Z0-9-]+)["\']', content)
            if match:
                return match.group(1)

            # Pattern 3: /scaninfo/XXX
            match = re.search(r'/scaninfo/([a-zA-Z0-9-]+)', content)
            if match:
                return match.group(1)

            raise SpiderFootAPIError(
                f"Could not extract scan ID from response. Target: {target}"
            )

        except requests.exceptions.RequestException as e:
            raise SpiderFootAPIError(f"Failed to start scan for {target}: {e}")

    def get_status(self, scan_id: str) -> ScanInfo:
        """
        Get the status of a scan.

        Args:
            scan_id: The scan ID returned from start_scan()

        Returns:
            ScanInfo object with scan details
        """
        try:
            response = self._get('/scanstatus', params={'id': scan_id})
            data = response.json()

            # Handle list response (some versions return a list)
            if isinstance(data, list) and len(data) > 0:
                data = data[0]

            return ScanInfo(
                scan_id=scan_id,
                name=data.get('name', ''),
                target=data.get('target', ''),
                status=ScanStatus(data.get('status', 'UNKNOWN')),
                created=data.get('created'),
                started=data.get('started'),
                ended=data.get('end'),
            )
        except (ValueError, KeyError) as e:
            raise SpiderFootAPIError(f"Invalid status response for scan {scan_id}: {e}")

    def get_scan_list(self) -> List[ScanInfo]:
        """
        Get list of all scans on the server.

        Returns:
            List of ScanInfo objects
        """
        try:
            response = self._get('/scanlist')
            data = response.json()

            scans = []
            for item in data:
                try:
                    scans.append(ScanInfo(
                        scan_id=item[0],      # ID
                        name=item[1],         # Name
                        target=item[2],       # Target
                        # NOTE: [5] is ended timestamp, [6] is status
                        status=ScanStatus(item[6]) if len(item) > 6 else ScanStatus.UNKNOWN,
                        created=item[3] if len(item) > 3 else None,
                        started=item[4] if len(item) > 4 else None,
                        ended=item[5] if len(item) > 5 else None,
                    ))
                except (IndexError, ValueError):
                    continue

            return scans
        except (ValueError, KeyError) as e:
            raise SpiderFootAPIError(f"Failed to get scan list: {e}")

    def stop_scan(self, scan_id: str) -> bool:
        """
        Stop a running scan.

        Args:
            scan_id: The scan ID to stop

        Returns:
            True if scan was stopped successfully
        """
        try:
            self._get('/stopscan', params={'id': scan_id})
            return True
        except SpiderFootAPIError:
            return False

    def stop_all_scans(self) -> int:
        """
        Stop all running scans on the server.

        Returns:
            Number of scans stopped
        """
        stopped = 0
        scans = self.get_scan_list()
        for scan in scans:
            if scan.status == ScanStatus.RUNNING:
                if self.stop_scan(scan.scan_id):
                    stopped += 1
        return stopped

    def delete_scan(self, scan_id: str) -> bool:
        """
        Delete a scan from the database.

        Args:
            scan_id: The scan ID to delete

        Returns:
            True if scan was deleted successfully
        """
        try:
            self._get('/scandelete', params={'id': scan_id})
            return True
        except SpiderFootAPIError:
            return False

    def get_results_csv(self, scan_id: str) -> str:
        """
        Get scan results as CSV.

        Args:
            scan_id: The scan ID to get results for

        Returns:
            CSV data as string
        """
        try:
            response = self._get(
                '/scaneventresultexport',
                params={'id': scan_id, 'filetype': 'csv'}
            )
            return response.text
        except SpiderFootAPIError as e:
            raise SpiderFootAPIError(f"Failed to export CSV for scan {scan_id}: {e}")

    def get_results_json(self, scan_id: str, event_type: Optional[str] = None) -> List[Dict]:
        """
        Get scan results as JSON.

        Args:
            scan_id: The scan ID to get results for
            event_type: Optional filter for specific event type

        Returns:
            List of event dictionaries
        """
        params = {'id': scan_id}
        if event_type:
            params['eventType'] = event_type

        try:
            response = self._get('/scaneventresults', params=params)
            return response.json()
        except (ValueError, SpiderFootAPIError) as e:
            raise SpiderFootAPIError(f"Failed to get results for scan {scan_id}: {e}")

    def wait_for_scan(
        self,
        scan_id: str,
        poll_interval: int = 10,
        timeout: Optional[int] = None,
        on_progress: Optional[callable] = None
    ) -> ScanInfo:
        """
        Wait for a scan to complete.

        Args:
            scan_id: The scan ID to wait for
            poll_interval: Seconds between status checks
            timeout: Maximum seconds to wait (None = no timeout)
            on_progress: Optional callback(ScanInfo) called on each poll

        Returns:
            Final ScanInfo when scan completes

        Raises:
            SpiderFootAPIError: If timeout exceeded or scan fails
        """
        start = time.time()
        while True:
            info = self.get_status(scan_id)

            if on_progress:
                on_progress(info)

            if info.status in (ScanStatus.FINISHED, ScanStatus.ABORTED, ScanStatus.ERROR):
                return info

            if timeout and (time.time() - start) > timeout:
                raise SpiderFootAPIError(f"Timeout waiting for scan {scan_id}")

            time.sleep(poll_interval)

    def get_running_count(self) -> int:
        """
        Get count of currently running scans.

        Returns:
            Number of scans in RUNNING status
        """
        scans = self.get_scan_list()
        return sum(1 for s in scans if s.status == ScanStatus.RUNNING)

    def get_scan_summary(self) -> Dict[str, int]:
        """
        Get summary counts of scans by status.

        Returns:
            Dict mapping status names to counts
        """
        scans = self.get_scan_list()
        summary = {}
        for scan in scans:
            status_name = scan.status.value
            summary[status_name] = summary.get(status_name, 0) + 1
        return summary


def create_api_client(host: str, port: int = 5001) -> SpiderFootAPI:
    """
    Factory function to create SpiderFoot API client.

    Args:
        host: Worker hostname or IP
        port: SpiderFoot web server port

    Returns:
        Configured SpiderFootAPI instance
    """
    return SpiderFootAPI(host, port)

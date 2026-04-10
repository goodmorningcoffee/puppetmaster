/* ============================================================================
 * sse.js — Server-Sent Events client for vitals + scan status.
 *
 * Opens an EventSource connection to /events/vitals and updates the status
 * line in the page header (CPU/MEM/DISK bars + scan status text).
 *
 * If the SSE endpoint fails or disconnects, the browser's EventSource
 * automatically reconnects with exponential backoff.
 * ============================================================================ */

(function () {
  'use strict';

  /**
   * Update a single vital bar (CPU / MEM / DISK) with a percentage value.
   * Adds .warn / .crit classes for color coding above thresholds.
   */
  function updateVital(id, percent) {
    const el = document.getElementById(id);
    if (!el) return;
    const fill = el.querySelector('.fill');
    const pct = el.querySelector('.pct');
    if (fill) fill.style.width = `${Math.max(0, Math.min(100, percent))}%`;
    if (pct) pct.textContent = `${percent.toFixed(0)}%`;
    el.classList.remove('warn', 'crit');
    if (percent >= 90) el.classList.add('crit');
    else if (percent >= 70) el.classList.add('warn');
  }

  /**
   * Update the scan status text in the header.
   */
  function updateScanStatus(running, stats) {
    const el = document.getElementById('scan-status');
    if (!el) return;
    if (!running) {
      el.textContent = 'Idle';
      el.className = 'value';
      return;
    }
    if (stats) {
      const progress = (stats.completed || 0) + (stats.failed || 0);
      const total = stats.total || 0;
      const current = stats.current_domain || 'unknown';
      el.textContent = `SCAN ${progress}/${total} — ${current}`;
      el.className = 'value cp-yellow';
    } else {
      el.textContent = 'SCAN running';
      el.className = 'value cp-yellow';
    }
  }

  /**
   * Open the SSE connection. Idempotent — only one connection per page.
   */
  let eventSource = null;
  function connect() {
    if (eventSource) return;

    try {
      eventSource = new EventSource('/events/vitals');
    } catch (e) {
      console.error('Failed to open SSE connection:', e);
      return;
    }

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.error) {
          console.warn('SSE error event:', data.error);
          return;
        }
        if (typeof data.cpu === 'number') updateVital('vital-cpu', data.cpu);
        if (typeof data.mem === 'number') updateVital('vital-mem', data.mem);
        if (typeof data.disk === 'number') updateVital('vital-disk', data.disk);
        updateScanStatus(data.scan_running || false, data.scan_stats || null);
      } catch (e) {
        console.error('Failed to parse SSE event:', e, event.data);
      }
    };

    eventSource.onerror = (err) => {
      // EventSource auto-reconnects, so we just log here
      console.warn('SSE connection error (will auto-reconnect):', err);
    };
  }

  // Connect on page load
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', connect);
  } else {
    connect();
  }
})();

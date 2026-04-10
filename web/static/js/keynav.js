/* ============================================================================
 * keynav.js — Arrow-key navigation for the cyberpunk web GUI.
 *
 * Provides TUI-style keyboard navigation:
 *   - Arrow Down / Tab        — focus next .cp-menu-item
 *   - Arrow Up / Shift+Tab    — focus previous .cp-menu-item
 *   - Enter / Space           — activate (click) the focused item
 *   - Escape                  — go back to previous page
 *   - Number keys 1-9, 0      — jump to menu item by [N] key prefix
 *   - Letter keys             — jump to menu item by [letter] key prefix
 *
 * The script is intentionally vanilla — no jQuery, no framework, no build
 * step. It targets all elements with class .cp-menu-item.
 * ============================================================================ */

(function () {
  'use strict';

  /**
   * Get all currently visible menu items in document order.
   */
  function getMenuItems() {
    return Array.from(document.querySelectorAll('.cp-menu-item'))
      .filter(el => el.offsetParent !== null);  // skip hidden items
  }

  /**
   * Find the index of the currently-focused menu item, or -1 if none.
   */
  function getFocusedIndex(items) {
    const active = document.activeElement;
    return items.indexOf(active);
  }

  /**
   * Move focus to the menu item at the given index, wrapping around.
   */
  function focusItem(items, index) {
    if (items.length === 0) return;
    const wrapped = ((index % items.length) + items.length) % items.length;
    items[wrapped].focus();
  }

  /**
   * Find a menu item by its data-key attribute (case-insensitive).
   * Returns the element or null.
   */
  function findItemByKey(items, key) {
    const lower = key.toLowerCase();
    return items.find(el => (el.dataset.key || '').toLowerCase() === lower) || null;
  }

  /**
   * Main keydown handler — installed on document.
   */
  function onKeyDown(event) {
    // Don't intercept keys when the user is typing in an input/textarea
    const tag = (event.target.tagName || '').toLowerCase();
    if (tag === 'input' || tag === 'textarea' || tag === 'select') {
      return;
    }

    const items = getMenuItems();
    if (items.length === 0) return;

    const currentIndex = getFocusedIndex(items);

    switch (event.key) {
      case 'ArrowDown':
      case 'j':  // vim-style
        event.preventDefault();
        focusItem(items, currentIndex < 0 ? 0 : currentIndex + 1);
        break;

      case 'ArrowUp':
      case 'k':  // vim-style
        event.preventDefault();
        focusItem(items, currentIndex < 0 ? items.length - 1 : currentIndex - 1);
        break;

      case 'Home':
        event.preventDefault();
        focusItem(items, 0);
        break;

      case 'End':
        event.preventDefault();
        focusItem(items, items.length - 1);
        break;

      case 'Enter':
      case ' ':
        // Default focus behavior already handles Enter on a button — but
        // we still need to prevent the body from scrolling on Space
        if (event.key === ' ' && currentIndex >= 0) {
          event.preventDefault();
          items[currentIndex].click();
        }
        break;

      case 'Escape':
        // Go back if there's history; otherwise, go to home
        event.preventDefault();
        if (window.history.length > 1) {
          window.history.back();
        } else {
          window.location.href = '/';
        }
        break;

      default:
        // Try to match by data-key (number / letter shortcuts)
        // Only single-character keys (don't catch modifier combos)
        if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
          const item = findItemByKey(items, event.key);
          if (item) {
            event.preventDefault();
            item.focus();
            item.click();
          }
        }
    }
  }

  document.addEventListener('keydown', onKeyDown);
})();

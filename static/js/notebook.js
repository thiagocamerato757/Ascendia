/*
 * Notebook workspace tabs (spec §10.4): on narrow screens the three columns
 * (sources | conversation | notes) become tabs. WAI-ARIA tabs pattern: arrow
 * keys move between tabs, only the selected tab is in the tab order. Without
 * JS the columns simply stack; on wide screens CSS shows all three.
 */
(function () {
  'use strict';

  function init(tablist) {
    var layout = document.querySelector('.l-notebook');
    if (!layout) return;
    var tabs = Array.prototype.slice.call(tablist.querySelectorAll('[role=tab]'));

    function select(tab, focus) {
      tabs.forEach(function (t) {
        var on = t === tab;
        t.setAttribute('aria-selected', on ? 'true' : 'false');
        t.tabIndex = on ? 0 : -1;
      });
      layout.setAttribute('data-active-tab', tab.getAttribute('data-tab'));
      if (focus) tab.focus();
    }

    tabs.forEach(function (tab, i) {
      tab.addEventListener('click', function () { select(tab, false); });
      tab.addEventListener('keydown', function (event) {
        var next = null;
        if (event.key === 'ArrowRight') next = tabs[(i + 1) % tabs.length];
        if (event.key === 'ArrowLeft') next = tabs[(i - 1 + tabs.length) % tabs.length];
        if (event.key === 'Home') next = tabs[0];
        if (event.key === 'End') next = tabs[tabs.length - 1];
        if (next) { event.preventDefault(); select(next, true); }
      });
    });
    var current = tablist.querySelector('[aria-selected=true]') || tabs[0];
    tablist.hidden = false; // tabs only exist with JS; without it the columns stack
    select(current, false);
  }

  document.addEventListener('DOMContentLoaded', function () {
    var tablist = document.querySelector('[data-notebook-tabs]');
    if (tablist) init(tablist);
  });
})();

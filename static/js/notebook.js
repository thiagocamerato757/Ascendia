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

/*
 * Sources dropzone: drop or choose several PDFs; HTMX sends them as soon as the
 * input changes (hx-trigger on the form) and the panel shows upload progress.
 * The panel is replaced after every upload, so listeners are delegated.
 */
(function () {
  'use strict';

  function zoneOf(target) { return target && target.closest ? target.closest('[data-dropzone]') : null; }

  ['dragenter', 'dragover'].forEach(function (type) {
    document.addEventListener(type, function (event) {
      var zone = zoneOf(event.target);
      if (!zone) return;
      event.preventDefault();
      zone.classList.add('is-dragging');
    });
  });
  document.addEventListener('dragleave', function (event) {
    var zone = zoneOf(event.target);
    if (zone && !zone.contains(event.relatedTarget)) zone.classList.remove('is-dragging');
  });
  document.addEventListener('drop', function (event) {
    var zone = zoneOf(event.target);
    if (!zone) return;
    event.preventDefault();
    zone.classList.remove('is-dragging');
    var input = zone.querySelector('input[type=file]');
    if (!input || !event.dataTransfer || !event.dataTransfer.files.length) return;
    input.files = event.dataTransfer.files; // the server checks each file (type, size, content)
    input.dispatchEvent(new Event('change', { bubbles: true }));
  });

  document.addEventListener('htmx:beforeRequest', function (event) {
    var zone = event.detail.elt;
    if (!zone.matches || !zone.matches('[data-dropzone]')) return;
    var count = (zone.querySelector('input[type=file]').files || []).length;
    var text = count === 1 ? zone.dataset.uploadingOne : (zone.dataset.uploadingMany || '').replace('%(n)s', count);
    zone.classList.add('is-uploading');
    zone.querySelector('[data-dropzone-status]').textContent = text;
    zone.querySelector('[data-dropzone-progress]').hidden = false;
  });
  document.addEventListener('htmx:xhr:progress', function (event) {
    var zone = event.detail.elt;
    if (!zone.matches || !zone.matches('[data-dropzone]') || !event.detail.total) return;
    zone.querySelector('[data-dropzone-bar]').value = Math.round((event.detail.loaded / event.detail.total) * 100);
  });
  document.addEventListener('htmx:afterRequest', function (event) {
    var zone = event.detail.elt;
    if (zone.matches && zone.matches('[data-dropzone]') && zone.isConnected) {
      zone.classList.remove('is-uploading'); // only matters if the panel was not replaced (network error)
      zone.querySelector('[data-dropzone-progress]').hidden = true;
    }
  });
})();


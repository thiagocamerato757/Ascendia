/*
 * Ascendia chat (spec §7.5, §10.5).
 *
 * Streaming: an assistant bubble with data-stream-url opens an EventSource when
 * it appears (after an HTMX swap or on page load, so a reload resumes it):
 *   html  -> the answer so far, already sanitized HTML from the server
 *   done  -> the final bubble (validated citations + copy actions) replaces it
 *   error -> the message in a notice
 * Stop asks the server to stop; the stream then ends with "done".
 *
 * Scrolling: the log follows new text only while the reader is at the bottom;
 * scrolling up to reread is never interrupted, and "Jump to latest" appears.
 *
 * Copy: "Copy Markdown" / "Copy formatted" read <template data-copy-source>.
 * Uses the Clipboard API when available (secure contexts) and falls back to a
 * selection + execCommand('copy') when self-hosted over plain HTTP.
 */
(function () {
  'use strict';

  var NEAR_BOTTOM_PX = 80;
  var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function log() { return document.getElementById('chat-log'); }
  function panel() { return document.getElementById('chat-panel'); }

  function csrfToken() {
    var input = document.querySelector('#ask-form [name=csrfmiddlewaretoken]');
    return input ? input.value : '';
  }

  // ---------------------------------------------------------------- scrolling
  function isNearBottom(el) {
    return el.scrollHeight - el.scrollTop - el.clientHeight <= NEAR_BOTTOM_PX;
  }

  function scrollToBottom(smooth) {
    var el = log();
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: smooth && !reduceMotion ? 'smooth' : 'auto' });
    setJump(false);
  }

  function setJump(visible) {
    var button = document.querySelector('[data-chat-jump]');
    if (button) button.hidden = !visible;
  }

  /** Run a DOM update; keep following the bottom only if the reader was there. */
  function updateKeepingPosition(fn) {
    var el = log();
    var follow = !el || isNearBottom(el);
    fn();
    if (!el) return;
    if (follow) el.scrollTop = el.scrollHeight;
    else setJump(true);
  }

  // ---------------------------------------------------------------- streaming
  function setBusy(busy) {
    var el = log();
    if (el) el.setAttribute('aria-busy', busy ? 'true' : 'false');
    var button = document.querySelector('#ask-form button[type=submit]');
    if (button) button.disabled = busy;
  }

  function showError(bubble, message) {
    var notice = document.createElement('div');
    notice.className = 'c-notice c-notice--danger';
    notice.setAttribute('role', 'alert');
    var icon = document.createElement('span');
    icon.className = 'c-notice__icon';
    var body = document.createElement('div');
    body.className = 'c-notice__body';
    var text = document.createElement('p');
    text.className = 'c-notice__message';
    text.textContent = message; // never innerHTML: the message is server text
    body.appendChild(text);
    notice.appendChild(icon);
    notice.appendChild(body);
    bubble.appendChild(notice);
  }

  function connect(bubble) {
    var url = bubble.getAttribute('data-stream-url');
    if (!url || bubble.dataset.connected) return;
    bubble.dataset.connected = '1';
    var body = bubble.querySelector('.c-message__body');
    var source = new EventSource(url);
    setBusy(true);

    function finish() {
      source.close();
      bubble.removeAttribute('data-stream-url');
      var stop = bubble.querySelector('[data-stop]');
      if (stop) stop.remove();
      setBusy(false);
    }

    source.addEventListener('html', function (event) {
      var data = JSON.parse(event.data);
      updateKeepingPosition(function () {
        body.innerHTML = data.html; // sanitized by the server
        window.AscendiaRich.enhance(body); // math + code blocks
      });
    });
    source.addEventListener('done', function (event) {
      var data = JSON.parse(event.data);
      finish();
      updateKeepingPosition(function () {
        var holder = document.createElement('div');
        holder.innerHTML = data.bubble; // server-rendered template, answer sanitized with nh3
        var fresh = holder.firstElementChild;
        if (fresh) {
          bubble.replaceWith(fresh);
          if (window.htmx) window.htmx.process(fresh);
          window.AscendiaRich.enhance(fresh);
        }
      });
    });
    source.addEventListener('error', function (event) {
      var message = event.data ? JSON.parse(event.data).message
        : ((panel() && panel().dataset.connectionLost) || 'Connection lost.');
      finish();
      updateKeepingPosition(function () {
        if (body.querySelector('.c-typing')) body.textContent = '';
        showError(bubble, message);
      });
    });

    var stop = bubble.querySelector('[data-stop]');
    if (stop) {
      stop.addEventListener('click', function () {
        stop.disabled = true;
        fetch(bubble.getAttribute('data-stop-url'), {
          method: 'POST', headers: { 'X-CSRFToken': csrfToken() }, credentials: 'same-origin',
        });
      });
    }
  }

  function connectWithin(root) {
    if (!root || !root.querySelectorAll) return;
    if (root.matches && root.matches('[data-stream-url]')) connect(root);
    root.querySelectorAll('[data-stream-url]').forEach(connect);
  }

  // ---------------------------------------------------------------- copying
  function copyMarkdown(text) { return window.AscendiaRich.copyText(text); }

  function copyRich(html, plain) { return window.AscendiaRich.copyHtml(html, plain); }


  function onCopy(button) {
    var actions = button.closest('[data-copy-actions]');
    var source = function (kind) { return actions.querySelector('template[data-copy-source="' + kind + '"]'); };
    var markdown = source('markdown').content.textContent;
    var status = actions.querySelector('[data-copy-status]');
    var done = panel() ? panel().dataset : {};
    var job = button.dataset.copy === 'rich'
      ? copyRich(source('rich').innerHTML, markdown)
      : copyMarkdown(markdown);
    job.then(function () { status.textContent = done.copied || 'Copied'; })
      .catch(function () { status.textContent = done.copyFailed || 'Could not copy'; })
      .then(function () { setTimeout(function () { status.textContent = ''; }, 2000); });
  }

  // ---------------------------------------------------------------- wiring
  document.addEventListener('DOMContentLoaded', function () {
    connectWithin(document);
    scrollToBottom(false);
    var el = log();
    if (el) el.addEventListener('scroll', function () { if (isNearBottom(el)) setJump(false); }, { passive: true });
  });

  document.addEventListener('htmx:afterSettle', function (event) {
    connectWithin(event.target);
    if (event.target.id === 'chat-log') {
      var empty = event.target.querySelector('[data-chat-empty]');
      if (empty) empty.remove();
      var form = document.getElementById('ask-form');
      if (form) form.reset();
      var error = document.getElementById('ask-error');
      if (error) error.innerHTML = '';
      scrollToBottom(true); // the user just asked: always show their question
    }
    if (event.target.id === 'chat-panel') {
      var newLog = log();
      if (newLog) newLog.addEventListener('scroll', function () { if (isNearBottom(newLog)) setJump(false); }, { passive: true });
    }
    if (event.target.id === 'citation-viewer') {
      document.querySelectorAll('.c-source-item.is-highlighted').forEach(function (el) {
        el.classList.remove('is-highlighted');
      });
      var card = event.target.querySelector('[data-source-id]');
      var id = card && card.getAttribute('data-source-id');
      var item = id && document.getElementById('source-' + id);
      if (item) { item.classList.add('is-highlighted'); item.scrollIntoView({ block: 'nearest' }); }
    }
  });

  document.addEventListener('click', function (event) {
    var copy = event.target.closest('[data-copy]');
    if (copy) { onCopy(copy); return; }
    if (event.target.closest('[data-chat-jump]')) { scrollToBottom(true); return; }
    if (event.target.closest('[data-close-citation]')) {
      var viewer = document.getElementById('citation-viewer');
      if (viewer) viewer.innerHTML = '';
      document.querySelectorAll('.c-source-item.is-highlighted').forEach(function (el) {
        el.classList.remove('is-highlighted');
      });
    }
  });

  // The question box grows with its text (up to the CSS max-height), then scrolls.
  function autoGrow(input) {
    input.style.height = 'auto';
    input.style.height = input.scrollHeight + 'px';
  }
  document.addEventListener('input', function (event) {
    if (event.target.id === 'ask-question') autoGrow(event.target);
  });
  document.addEventListener('reset', function (event) {
    var input = event.target.querySelector && event.target.querySelector('#ask-question');
    if (input) setTimeout(function () { input.style.height = ''; }, 0);
  });

  // Enter sends, Shift+Enter adds a line.
  document.addEventListener('keydown', function (event) {
    var input = event.target;
    if (input.id !== 'ask-question' || event.key !== 'Enter' || event.shiftKey || event.isComposing) return;
    event.preventDefault();
    if (input.value.trim()) input.form.requestSubmit();
  });
})();

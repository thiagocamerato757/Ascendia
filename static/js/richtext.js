/*
 * Rich text in answers and passages: math (KaTeX) and code blocks.
 *
 * The server already sanitized the HTML (nh3) and left:
 *   <span class="math inline">TeX</span> / <div class="math block">TeX</div>  (TeX escaped)
 *   <pre><code class="language-x"> with Pygments tok-* spans
 * enhance(root) renders the math with KaTeX (trust: false, so no \href/\url
 * links or raw HTML) and gives each code block a bar with its language and a
 * "Copy code" button. Safe to call repeatedly (streaming re-renders often).
 *
 * copyText(text) is shared with chat.js: Clipboard API when available, else a
 * selection + execCommand fallback (self-hosted over plain HTTP).
 */
(function () {
  'use strict';

  function label(name, fallback) {
    var holder = document.querySelector('[data-richtext-labels]');
    return (holder && holder.dataset[name]) || fallback;
  }

  // ------------------------------------------------------------------ copying
  function legacyCopy(node) {
    var holder = document.createElement('div');
    holder.setAttribute('contenteditable', 'true');
    holder.style.cssText = 'position:fixed;left:-9999px;top:0;opacity:0;white-space:pre-wrap';
    holder.appendChild(node);
    document.body.appendChild(holder);
    var range = document.createRange();
    range.selectNodeContents(holder);
    var selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    var ok = false;
    try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
    selection.removeAllRanges();
    holder.remove();
    return ok;
  }

  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(text);
    var pre = document.createElement('pre');
    pre.textContent = text;
    return legacyCopy(pre) ? Promise.resolve() : Promise.reject(new Error('copy failed'));
  }

  /** Formatted copy: text/html + text/plain, or a rich selection over plain HTTP. */
  function copyHtml(html, plain) {
    if (navigator.clipboard && window.isSecureContext && window.ClipboardItem) {
      return navigator.clipboard.write([new ClipboardItem({
        'text/html': new Blob([html], { type: 'text/html' }),
        'text/plain': new Blob([plain], { type: 'text/plain' }),
      })]);
    }
    var div = document.createElement('div');
    div.innerHTML = html; // sanitized server-side (nh3)
    return legacyCopy(div) ? Promise.resolve() : Promise.reject(new Error('copy failed'));
  }

  // ------------------------------------------------------------------ math
  function renderMath(root) {
    if (!window.katex) return;
    root.querySelectorAll('.math:not([data-rendered])').forEach(function (el) {
      var tex = el.textContent;
      el.setAttribute('data-rendered', '');
      el.setAttribute('data-tex', tex); // keeps the source (copy, a11y fallback)
      try {
        window.katex.render(tex, el, {
          displayMode: el.classList.contains('block'),
          throwOnError: false, // an invalid formula shows its TeX in red instead of failing
          trust: false,
          strict: 'ignore',
          maxSize: 20,
          maxExpand: 500,
          output: 'htmlAndMathml', // MathML for screen readers
        });
      } catch (e) {
        el.textContent = tex;
      }
    });
  }

  // ------------------------------------------------------------------ code blocks
  function languageOf(code) {
    var match = /(?:^|\s)language-([\w+#.-]+)/.exec(code.className || '');
    return match ? match[1] : '';
  }

  function enhanceCode(root) {
    root.querySelectorAll('pre > code').forEach(function (code) {
      var pre = code.parentElement;
      if (pre.parentElement && pre.parentElement.classList.contains('c-code')) return;
      var box = document.createElement('div');
      box.className = 'c-code';
      var bar = document.createElement('div');
      bar.className = 'c-code__bar';
      var lang = document.createElement('span');
      lang.className = 'c-code__lang';
      lang.textContent = languageOf(code) || label('codeLabel', 'code');
      var button = document.createElement('button');
      button.type = 'button';
      button.className = 'c-code__copy';
      button.textContent = label('copyCode', 'Copy code');
      button.addEventListener('click', function () {
        copyText(code.textContent).then(function () {
          button.textContent = label('copied', 'Copied');
        }).catch(function () {
          button.textContent = label('copyFailed', 'Could not copy');
        }).then(function () {
          setTimeout(function () { button.textContent = label('copyCode', 'Copy code'); }, 2000);
        });
      });
      bar.appendChild(lang);
      bar.appendChild(button);
      pre.parentNode.insertBefore(box, pre);
      box.appendChild(bar);
      box.appendChild(pre);
    });
  }

  function enhance(root) {
    if (!root || !root.querySelectorAll) return;
    renderMath(root);
    enhanceCode(root);
  }

  window.AscendiaRich = { enhance: enhance, copyText: copyText, copyHtml: copyHtml };

  document.addEventListener('DOMContentLoaded', function () { enhance(document); });
  document.addEventListener('htmx:afterSettle', function (event) { enhance(event.target); });
})();

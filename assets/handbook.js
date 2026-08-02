/* The Linux, Virtualization & DevOps Handbook — reader shell.
   Hash routing, full-text search, outline tracking, copy buttons, theme. */
(function () {
  'use strict';

  const app       = document.querySelector('.app');
  const nav       = document.querySelector('.nav');
  const navLinks  = Array.from(document.querySelectorAll('.nav-ch a'));
  const articles  = Array.from(document.querySelectorAll('.ch'));
  const railSets  = Array.from(document.querySelectorAll('.rail-set'));
  const bar       = document.querySelector('.progress span');
  const input     = document.querySelector('.search input');
  const results   = document.querySelector('.results');
  const scrim     = document.querySelector('.scrim');
  const navToggle = document.querySelector('.nav-toggle');
  const themeBtn  = document.querySelector('.theme-btn');

  const chapters = articles.map((a) => a.dataset.ch);
  const store = (() => {
    try { localStorage.getItem('hb'); return localStorage; } catch (e) { return null; }
  })();

  /* ---------------------------------------------------------------- theme */
  function applyTheme(mode) {
    if (mode === 'system') document.documentElement.removeAttribute('data-theme');
    else document.documentElement.setAttribute('data-theme', mode);
    if (store) { try { store.setItem('hb-theme', mode); } catch (e) {} }
  }
  let theme = (store && store.getItem('hb-theme')) || 'system';
  if (theme !== 'system') applyTheme(theme);

  themeBtn.addEventListener('click', () => {
    const dark = document.documentElement.getAttribute('data-theme') === 'dark' ||
      (!document.documentElement.getAttribute('data-theme') &&
        matchMedia('(prefers-color-scheme: dark)').matches);
    theme = dark ? 'light' : 'dark';
    applyTheme(theme);
    // Re-render mermaid diagrams with new theme
    if (window.mermaid && window.getMermaidTheme) {
      Array.from(document.querySelectorAll('pre.mermaid')).forEach((el) => {
        if (el.querySelector('svg')) el.removeChild(el.querySelector('svg'));
      });
      window.mermaid.contentLoaded();
    }
  });

  /* --------------------------------------------------------------- router */
  function parseHash() {
    const raw = location.hash.replace(/^#/, '');
    if (!raw) return { ch: chapters[0], id: '' };
    const [ch, id] = raw.split('/');
    return { ch: chapters.includes(ch) ? ch : chapters[0], id: id || '' };
  }

  let current = null;

  function show(ch, id, push) {
    if (!chapters.includes(ch)) ch = chapters[0];
    if (ch !== current) {
      articles.forEach((a) => { a.hidden = a.dataset.ch !== ch; });
      railSets.forEach((r) => { r.hidden = r.dataset.ch !== ch; });
      navLinks.forEach((a) => {
        if (a.dataset.ch === ch) a.setAttribute('aria-current', 'page');
        else a.removeAttribute('aria-current');
      });
      const link = navLinks.find((a) => a.dataset.ch === ch);
      if (link) keepInView(link);
      current = ch;
      drawMermaid(articles.find((a) => a.dataset.ch === ch));
    }
    if (push) history.pushState(null, '', '#' + ch + (id ? '/' + id : ''));

    if (id) {
      const target = document.getElementById(id);
      if (target) {
        const y = target.getBoundingClientRect().top + scrollY - 78;
        scrollTo({ top: y, behavior: 'instant' });
      }
    } else {
      scrollTo({ top: 0, behavior: 'instant' });
    }
    progress();
    trackOutline();
    closeNav();
  }

  function keepInView(el) {
    const box = nav.getBoundingClientRect();
    const r = el.getBoundingClientRect();
    if (r.top < box.top + 8 || r.bottom > box.bottom - 8) {
      el.scrollIntoView({ block: 'center' });
    }
  }

  /* Mermaid renders on load; nudge it if a diagram in a freshly shown
     chapter still holds raw source instead of an <svg>. */
  function drawMermaid(article) {
    if (!article || !window.mermaid || typeof window.mermaid.run !== 'function') return;
    const pending = Array.from(article.querySelectorAll('pre.mermaid'))
      .filter((n) => !n.querySelector('svg'));
    if (!pending.length) return;
    try { window.mermaid.run({ nodes: pending, suppressErrors: true }); } catch (e) {}
    // Enable pan/zoom on rendered SVGs
    setTimeout(() => { enableSVGPanZoom(article); }, 100);
  }

  function enableSVGPanZoom(container) {
    if (!container) return;
    Array.from(container.querySelectorAll('.fig-mermaid svg')).forEach((svg) => {
      if (svg._panZoomEnabled) return;
      svg._panZoomEnabled = true;
      let tx = 0, ty = 0, scale = 1;
      const group = svg.querySelector('g') || svg;
      const parent = svg.parentElement;
      let isDragging = false, startX, startY;

      svg.addEventListener('wheel', (e) => {
        e.preventDefault();
        const delta = e.deltaY > 0 ? 0.9 : 1.1;
        scale = Math.max(0.5, Math.min(scale * delta, 3));
        group.style.transform = `translate(${tx}px, ${ty}px) scale(${scale})`;
      });

      svg.addEventListener('mousedown', (e) => {
        isDragging = true;
        startX = e.clientX - tx;
        startY = e.clientY - ty;
      });

      document.addEventListener('mousemove', (e) => {
        if (!isDragging || !parent.contains(svg)) return;
        tx = e.clientX - startX;
        ty = e.clientY - startY;
        group.style.transform = `translate(${tx}px, ${ty}px) scale(${scale})`;
      });

      document.addEventListener('mouseup', () => { isDragging = false; });
      svg.addEventListener('mouseleave', () => { isDragging = false; });
    });
  }

  addEventListener('hashchange', () => { const h = parseHash(); show(h.ch, h.id, false); });

  document.addEventListener('click', (e) => {
    const a = e.target.closest('a[href^="#"]');
    if (!a) return;
    const raw = a.getAttribute('href').slice(1);
    if (!raw) return;
    const [ch, id] = raw.split('/');
    if (!chapters.includes(ch)) return;              // in-page anchor, let it be
    e.preventDefault();
    show(ch, id || '', true);
    hideResults();
  });

  /* ------------------------------------------------------------- progress */
  function progress() {
    const art = articles.find((a) => !a.hidden);
    if (!art || !bar) return;
    const total = art.offsetHeight - innerHeight;
    const done = total > 40 ? Math.min(1, Math.max(0, (scrollY - art.offsetTop + 80) / total)) : 1;
    bar.style.width = (done * 100).toFixed(2) + '%';
  }

  /* -------------------------------------------------------------- outline */
  let headings = [];
  let railLinks = [];

  function collectOutline() {
    const set = railSets.find((r) => !r.hidden);
    railLinks = set ? Array.from(set.querySelectorAll('a')) : [];
    headings = railLinks
      .map((a) => document.getElementById(a.getAttribute('href').split('/')[1]))
      .filter(Boolean);
  }

  function trackOutline() {
    collectOutline();
    if (!headings.length) return;
    let active = 0;
    for (let i = 0; i < headings.length; i++) {
      if (headings[i].getBoundingClientRect().top <= 120) active = i;
    }
    railLinks.forEach((a, i) => a.classList.toggle('on', i === active));
    const on = railLinks[active];
    if (on) {
      const box = on.parentElement.parentElement.getBoundingClientRect();
      const r = on.getBoundingClientRect();
      if (r.top < box.top || r.bottom > box.bottom) on.scrollIntoView({ block: 'nearest' });
    }
  }

  let ticking = false;
  addEventListener('scroll', () => {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(() => { progress(); trackOutline(); ticking = false; });
  }, { passive: true });

  /* --------------------------------------------------------------- search */
  const index = [];
  articles.forEach((art) => {
    const ch = art.dataset.ch;
    const chTitle = art.querySelector('h1').textContent.replace(/^\d+/, '').trim();
    index.push({ ch, chTitle, id: '', heading: chTitle, kind: 'chapter', body: '' });
    art.querySelectorAll('h2, h3, h4').forEach((h) => {
      const id = h.id;
      if (!id) return;
      const parts = [];
      let n = h.nextElementSibling;
      while (n && !/^H[1-4]$/.test(n.tagName)) {
        parts.push(n.textContent);
        n = n.nextElementSibling;
      }
      index.push({
        ch, chTitle, id,
        heading: h.textContent.replace(/#$/, '').trim(),
        kind: h.tagName.toLowerCase(),
        body: parts.join(' ').replace(/\s+/g, ' ').slice(0, 1600)
      });
    });
  });

  function esc(s) { return s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }

  function mark(text, q) {
    const i = text.toLowerCase().indexOf(q);
    if (i < 0) return esc(text.slice(0, 120));
    const from = Math.max(0, i - 46);
    const slice = text.slice(from, from + 150);
    const rel = i - from;
    return (from ? '…' : '') + esc(slice.slice(0, rel)) +
      '<mark>' + esc(slice.slice(rel, rel + q.length)) + '</mark>' +
      esc(slice.slice(rel + q.length));
  }

  let hits = [];
  let cursor = -1;

  function search(qRaw) {
    const q = qRaw.trim().toLowerCase();
    if (q.length < 2) { hideResults(); return; }
    hits = [];
    for (const row of index) {
      const h = row.heading.toLowerCase();
      const b = row.body.toLowerCase();
      let score = 0;
      if (h === q) score = 120;
      else if (h.startsWith(q)) score = 90;
      else if (h.includes(q)) score = 70;
      else if (b.includes(q)) score = 30;
      if (!score) continue;
      if (row.kind === 'chapter') score += 12;
      if (row.kind === 'h2') score += 6;
      hits.push({ row, score, snippet: h.includes(q) ? row.heading : mark(row.body, q) });
    }
    hits.sort((a, b) => b.score - a.score);
    hits = hits.slice(0, 24);
    cursor = hits.length ? 0 : -1;
    render(q);
  }

  function render(q) {
    if (!hits.length) {
      results.innerHTML = '<p class="r-none">No match for “' + esc(q) + '”</p>';
      results.hidden = false;
      return;
    }
    results.innerHTML = hits.map((hit, i) => {
      const r = hit.row;
      const href = '#' + r.ch + (r.id ? '/' + r.id : '');
      const label = r.kind === 'chapter'
        ? 'Chapter ' + r.ch
        : r.ch + ' · ' + r.chTitle;
      const snippet = r.heading.toLowerCase().includes(q)
        ? mark(r.heading, q)
        : esc(r.heading) + ' — <span class="r-body">' + hit.snippet + '</span>';
      return '<a href="' + href + '" class="' + (i === cursor ? 'on' : '') + '">' +
        '<span class="r-ch">' + esc(label) + '</span>' +
        '<span class="r-h">' + snippet + '</span></a>';
    }).join('');
    results.hidden = false;
  }

  function hideResults() { results.hidden = true; cursor = -1; }

  let t;
  input.addEventListener('input', () => { clearTimeout(t); t = setTimeout(() => search(input.value), 110); });
  input.addEventListener('focus', () => { if (input.value.trim().length > 1) search(input.value); });

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') { hideResults(); input.blur(); return; }
    if (results.hidden || !hits.length) return;
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      cursor = (cursor + (e.key === 'ArrowDown' ? 1 : -1) + hits.length) % hits.length;
      render(input.value.trim().toLowerCase());
      const on = results.querySelector('a.on');
      if (on) on.scrollIntoView({ block: 'nearest' });
    } else if (e.key === 'Enter' && cursor >= 0) {
      e.preventDefault();
      const r = hits[cursor].row;
      show(r.ch, r.id, true);
      hideResults();
      input.blur();
    }
  });

  document.addEventListener('click', (e) => {
    if (!e.target.closest('.search')) hideResults();
  });

  /* ------------------------------------------------------------ shortcuts */
  addEventListener('keydown', (e) => {
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName);
    if (e.key === '/' && !typing) { e.preventDefault(); input.focus(); input.select(); return; }
    if (typing || e.metaKey || e.ctrlKey || e.altKey) return;
    const i = chapters.indexOf(current);
    if (e.key === ']' && i < chapters.length - 1) show(chapters[i + 1], '', true);
    if (e.key === '[' && i > 0) show(chapters[i - 1], '', true);
  });

  /* ----------------------------------------------------------- mobile nav */
  function openNav()  { app.dataset.nav = 'open';  scrim.hidden = false; navToggle.setAttribute('aria-expanded', 'true'); }
  function closeNav() { delete app.dataset.nav;    scrim.hidden = true;  navToggle.setAttribute('aria-expanded', 'false'); }
  navToggle.addEventListener('click', () => (app.dataset.nav === 'open' ? closeNav() : openNav()));
  scrim.addEventListener('click', closeNav);

  /* --------------------------------------------------------------- copy */
  document.addEventListener('click', async (e) => {
    const btn = e.target.closest('.copy');
    if (!btn) return;
    const fig = btn.closest('.fig');
    const code = fig && fig.querySelector('pre');
    if (!code) return;
    try {
      await navigator.clipboard.writeText(code.innerText);
      btn.textContent = 'copied';
      btn.dataset.done = '1';
      setTimeout(() => { btn.textContent = 'copy'; delete btn.dataset.done; }, 1400);
    } catch (err) {
      btn.textContent = 'select it';
      setTimeout(() => { btn.textContent = 'copy'; }, 1400);
    }
  });

  /* ----------------------------------------------------------------- boot */
  const h = parseHash();
  show(h.ch, h.id, false);
  if (!location.hash) {
    history.replaceState(null, '', '#' + h.ch);
  }
})();

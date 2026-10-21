/* SGR · interacciones del prototipo navegable.
   Solo da vida a la maqueta: transiciones entre páginas, filtros, avisos y estados.
   En Django estas acciones las resuelve el servidor; el comportamiento visual se mantiene. */
(function () {
  'use strict';
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var hasViewTransitions = 'CSSViewTransitionRule' in window && /^https?:$/.test(location.protocol);
  var CHECK = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m5 12.5 4.5 4.5L19 7.5"/></svg>';
  var EYE_OFF = '<svg class="i" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 3l18 18"/><path d="M10.6 5.7A9.7 9.7 0 0 1 12 5.5c6 0 9.5 6.5 9.5 6.5a17 17 0 0 1-3 3.8M6.3 7.4A17 17 0 0 0 2.5 12S6 18.5 12 18.5a9.4 9.4 0 0 0 4.2-1"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/></svg>';

  /* ---------- paso suave entre páginas ---------- */
  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a[href]');
    if (!a || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || a.target) return;
    var href = a.getAttribute('href');
    if (href === '#') { e.preventDefault(); return; }
    if (!/\.html(#.*)?$/.test(href) || hasViewTransitions || reduce) return;
    e.preventDefault();
    document.body.classList.add('is-leaving');
    setTimeout(function () { location.href = href; }, 170);
  });
  window.addEventListener('pageshow', function () { document.body.classList.remove('is-leaving'); });

  /* ---------- avisos tipo toast ---------- */
  var stack;
  function toast(msg, sub) {
    if (!stack) { stack = document.createElement('div'); stack.className = 'toast-stack'; stack.setAttribute('role', 'status'); stack.setAttribute('aria-live', 'polite'); document.body.appendChild(stack); }
    var t = document.createElement('div');
    t.className = 'toast';
    t.innerHTML = '<span class="ok-ic">' + CHECK + '</span><div style="flex:1"><b></b><div class="sub"></div></div>';
    t.querySelector('b').textContent = msg;
    if (sub) t.querySelector('.sub').textContent = sub; else t.querySelector('.sub').remove();
    stack.appendChild(t);
    setTimeout(function () { t.classList.add('out'); setTimeout(function () { t.remove(); }, 300); }, 3200);
  }
  window.sgrToast = toast;

  document.addEventListener('click', function (e) {
    var b = e.target.closest && e.target.closest('[data-toast]');
    if (!b || b.disabled) return;
    toast(b.getAttribute('data-toast'), b.getAttribute('data-toast-sub'));
  });

  /* ---------- formulario con errores: el resumen tiembla y se muestra ---------- */
  document.addEventListener('click', function (e) {
    var b = e.target.closest && e.target.closest('[data-shake]');
    if (!b) return;
    var el = document.querySelector(b.getAttribute('data-shake'));
    if (!el) return;
    el.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'center' });
    el.classList.remove('shake'); void el.offsetWidth; el.classList.add('shake');
  });

  /* ---------- cifras que cuentan hasta su valor ---------- */
  function countUp(el) {
    var node = el.firstChild;
    while (node && (node.nodeType !== 3 || !node.textContent.trim())) node = node.nextSibling;
    if (!node) return;
    var raw = node.textContent.trim();
    if (!/^\d+(,\d+)?$/.test(raw)) return;
    var dec = raw.indexOf(',') > -1 ? raw.split(',')[1].length : 0;
    var target = parseFloat(raw.replace(',', '.'));
    var lead = node.textContent.match(/^\s*/)[0], trail = node.textContent.match(/\s*$/)[0];
    var start = null, dur = 900;
    function fmt(v) { return v.toFixed(dec).replace('.', ','); }
    function step(ts) {
      if (start === null) start = ts;
      var p = Math.min((ts - start) / dur, 1), e = 1 - Math.pow(1 - p, 3);
      node.textContent = lead + fmt(target * e) + trail;
      if (p < 1) requestAnimationFrame(step);
    }
    node.textContent = lead + fmt(0) + trail;
    setTimeout(function () { requestAnimationFrame(step); }, 200);
  }
  if (!reduce) document.querySelectorAll('.hero-num, .kpi .val').forEach(countUp);

  /* ---------- opciones tipo tarjeta (radio y checkbox) ---------- */
  document.addEventListener('change', function (e) {
    var t = e.target;
    if (t.type === 'radio' && t.closest('.opt')) {
      document.querySelectorAll('input[type=radio][name="' + t.name + '"]').forEach(function (r) {
        var o = r.closest('.opt'); if (o) o.classList.toggle('on', r.checked);
      });
    }
    if (t.type === 'checkbox' && t.closest('.check')) t.closest('.check').classList.toggle('on', t.checked);
  });

  /* ---------- filtros por estado (Mis actividades) ---------- */
  document.querySelectorAll('[data-filter-group]').forEach(function (group) {
    var table = document.querySelector(group.getAttribute('data-filter-group'));
    if (!table) return;
    var rows = table.querySelectorAll('tbody tr[data-state]');
    var empty = table.querySelector('tr.empty-row');
    var counter = document.querySelector('[data-filter-count]');
    group.addEventListener('click', function (e) {
      var a = e.target.closest('[data-filter]');
      if (!a) return;
      e.preventDefault();
      group.querySelectorAll('[data-filter]').forEach(function (x) { x.setAttribute('aria-current', x === a ? 'true' : 'false'); });
      var f = a.getAttribute('data-filter'), n = 0;
      rows.forEach(function (r) {
        var show = f === 'todas' || r.getAttribute('data-state') === f;
        r.hidden = !show;
        if (show) { n++; r.classList.remove('is-in'); void r.offsetWidth; r.classList.add('is-in'); }
      });
      if (empty) { empty.hidden = n !== 0; if (n === 0) { empty.classList.remove('is-in'); void empty.offsetWidth; empty.classList.add('is-in'); } }
      if (counter) counter.textContent = n === 1 ? '1 actividad' : n + ' actividades';
    });
  });
  document.addEventListener('click', function (e) {
    var b = e.target.closest && e.target.closest('[data-filter-reset]');
    if (!b) return;
    var all = document.querySelector('[data-filter="todas"]');
    if (all) all.click();
  });

  /* ---------- marcar alertas como revisadas ---------- */
  function bump(key, delta) {
    document.querySelectorAll('[data-count="' + key + '"]').forEach(function (c) {
      var v = Math.max(0, parseInt(c.textContent, 10) + delta);
      c.textContent = v;
      c.classList.remove('changed'); void c.offsetWidth; c.classList.add('changed');
      if (v === 0) c.style.visibility = 'hidden';
    });
  }
  document.addEventListener('click', function (e) {
    var b = e.target.closest && e.target.closest('[data-dismiss]');
    if (!b) return;
    var li = b.closest('li');
    if (!li) return;
    li.classList.add('is-collapsing');
    li.style.height = li.offsetHeight + 'px';
    li.classList.add('is-out');
    setTimeout(function () { li.style.height = '0px'; li.style.paddingTop = '0px'; li.style.paddingBottom = '0px'; li.style.borderTopWidth = '0px'; }, 180);
    setTimeout(function () { li.remove(); }, 520);
    bump('alertas', -1);
    var tab = document.querySelector('[data-count="alertas-tab"]');
    if (tab) tab.textContent = Math.max(0, parseInt(tab.textContent, 10) - 1);
    var rev = document.querySelector('[data-count="revisadas"]');
    if (rev) rev.textContent = parseInt(rev.textContent, 10) + 1;
    toast('Alerta marcada como revisada', 'El evento original se conserva en el historial.');
  });

  /* ---------- cambiar estado de un compromiso ---------- */
  var FLOW = { 'Ingresado': ['Pendiente'], 'Pendiente': ['En proceso'], 'En proceso': ['Realizado', 'Pendiente'] };
  var ALL = ['Ingresado', 'Pendiente', 'En proceso', 'Realizado'];
  var CLS = { 'Ingresado': 'chip line', 'Pendiente': 'chip', 'En proceso': 'chip info', 'Realizado': 'chip ok' };
  var menu;
  function closeMenu() { if (menu) { menu.remove(); menu = null; } }
  document.addEventListener('click', function (e) {
    var chip = e.target.closest && e.target.closest('.chip.state');
    if (menu && !(e.target.closest && e.target.closest('.state-menu'))) { var was = menu.chip; closeMenu(); if (was === chip) return; }
    if (!chip) return;
    var current = chip.firstChild.textContent.trim();
    var allowed = FLOW[current] || [];
    menu = document.createElement('div');
    menu.className = 'state-menu';
    menu.chip = chip;
    menu.innerHTML = '<div class="hd">Cambiar estado</div>';
    ALL.forEach(function (s) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.textContent = s;
      var note = document.createElement('span');
      note.className = 'note';
      if (s === current) { btn.disabled = true; note.textContent = 'actual'; }
      else if (allowed.indexOf(s) === -1) { btn.disabled = true; note.textContent = 'no permitido'; }
      btn.appendChild(note);
      btn.addEventListener('click', function () {
        var code = (chip.getAttribute('aria-label') || '').match(/COM-\d+/);
        chip.firstChild.textContent = s;
        chip.className = CLS[s] + ' state changed';
        chip.setAttribute('aria-label', 'Cambiar estado de ' + (code ? code[0] : 'compromiso') + ': ' + s);
        closeMenu();
        toast((code ? code[0] : 'Compromiso') + ' pasó a ' + s, 'Queda registrado quién lo cambió y cuándo.');
      });
      menu.appendChild(btn);
    });
    document.body.appendChild(menu);
    var r = chip.getBoundingClientRect();
    menu.style.top = (window.scrollY + r.bottom + 6) + 'px';
    menu.style.left = Math.min(window.scrollX + r.left, window.scrollX + document.documentElement.clientWidth - 236) + 'px';
  });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeMenu(); });

  /* ---------- mostrar u ocultar contraseña ---------- */
  document.querySelectorAll('.pw button').forEach(function (b) {
    var input = b.parentNode.querySelector('input'), eye = b.innerHTML;
    b.addEventListener('click', function () {
      var show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      b.innerHTML = show ? EYE_OFF : eye;
      b.setAttribute('aria-label', show ? 'Ocultar contraseña' : 'Mostrar contraseña');
    });
  });

  /* ---------- copiar código de verificación ---------- */
  document.querySelectorAll('.code button').forEach(function (b) {
    b.addEventListener('click', function () {
      var code = b.parentNode.textContent.trim();
      try { navigator.clipboard.writeText(code); } catch (err) { /* sin portapapeles: igual se avisa */ }
      toast('Código copiado', code);
    });
  });

  /* ---------- atajo "/" para buscar ---------- */
  document.addEventListener('keydown', function (e) {
    if (e.key !== '/' || /input|textarea|select/i.test(document.activeElement.tagName)) return;
    var s = document.querySelector('.top .search input');
    if (s) { e.preventDefault(); s.focus(); }
  });

  /* ---------- el elemento activo del menú siempre a la vista ---------- */
  var cur = document.querySelector('.nav [aria-current="page"]');
  if (cur && cur.scrollIntoView) cur.scrollIntoView({ block: 'nearest' });
})();

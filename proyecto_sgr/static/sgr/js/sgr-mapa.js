/* SGR · mapa de presencia territorial.

   Dibuja el mapa con SVG propio, sin servicios de mapas externos: no hay
   teselas que descargar ni claves que configurar, y funciona en cualquier
   red, también en la del municipio. Los datos son los mismos de la tabla
   que el servidor escribe debajo (gestion/mapa.py), así que si este archivo
   no carga no se pierde nada.

   Qué hay en el mapa
     · un círculo por territorio ubicado, en el centro aproximado que se
       escribió en su ficha; el color es el semáforo de la última presencia y
       el tamaño, las actividades del trimestre;
     · de fondo, cuando los territorios están en La Serena, una referencia
       aproximada de la costa, el río Elqui y la Plaza de Armas, para
       orientarse. No es cartografía: es un croquis.

   No hay casas ni direcciones: el mapa no recibe ninguna. */
(function () {
  'use strict';

  var fuente = document.getElementById('datos-mapa');
  var lienzo = document.getElementById('mapa-lienzo');
  var panel = document.getElementById('mapa-panel');
  var hoja = document.getElementById('mapa-hoja');
  if (!fuente || !lienzo || !panel) return;

  var datos;
  try { datos = JSON.parse(fuente.textContent); } catch (e) { return; }
  if (hoja) hoja.classList.add('con-js');

  var NS = 'http://www.w3.org/2000/svg';
  /* El dibujo se hace al tamaño real del recuadro: una unidad del SVG es un
     píxel de pantalla, así los nombres se leen igual en un teléfono que en
     el escritorio. Al cambiar el ancho de la ventana se vuelve a dibujar. */
  var ANCHO = 800, ALTO = 600;
  function medir() {
    ANCHO = Math.max(300, Math.round(lienzo.clientWidth || 800));
    ALTO = ANCHO < 640 ? Math.round(Math.max(320, ANCHO * 0.95)) : 600;
  }
  var reducir = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  var porId = {};
  datos.territorios.forEach(function (t) { porId[t.id] = t; });
  var ubicados = datos.territorios.filter(function (t) { return t.lat !== null && t.lng !== null; });

  /* ---------------------------------------------- referencia de La Serena
     Puntos aproximados (latitud, longitud), de sur a norte la costa y de la
     desembocadura hacia el valle el río. Basta para orientarse; no sirve
     para medir. */
  var SERENA = {
    caja: { latMin: -30.05, latMax: -29.75, lngMin: -71.42, lngMax: -71.05 },
    costa: [
      [-30.20, -71.42], [-29.985, -71.365], [-29.962, -71.348], [-29.952, -71.336],
      [-29.947, -71.318], [-29.944, -71.302], [-29.936, -71.292], [-29.924, -71.284],
      [-29.912, -71.278], [-29.905, -71.2745], [-29.896, -71.274], [-29.887, -71.276],
      [-29.876, -71.279], [-29.862, -71.283], [-29.845, -71.287], [-29.828, -71.291],
      [-29.810, -71.296], [-29.790, -71.300], [-29.60, -71.33]
    ],
    rio: [
      [-29.887, -71.276], [-29.8885, -71.266], [-29.890, -71.256], [-29.8915, -71.246],
      [-29.893, -71.236], [-29.8945, -71.226], [-29.896, -71.216], [-29.898, -71.205],
      [-29.901, -71.193], [-29.904, -71.180], [-29.907, -71.165], [-29.910, -71.150],
      [-29.913, -71.130], [-29.917, -71.100]
    ],
    lugares: [{ nombre: 'Plaza de Armas', lat: -29.9027, lng: -71.2519 }]
  };

  /* ------------------------------------------------------------ utilidades */

  function el(nombre, atributos, padre) {
    var nodo = document.createElementNS(NS, nombre);
    Object.keys(atributos || {}).forEach(function (k) { nodo.setAttribute(k, atributos[k]); });
    if (padre) padre.appendChild(nodo);
    return nodo;
  }

  function h(etiqueta, clase, texto) {
    var nodo = document.createElement(etiqueta);
    if (clase) nodo.className = clase;
    if (texto !== undefined && texto !== null) nodo.textContent = texto;
    return nodo;
  }

  function plural(n, uno, varios) { return n + ' ' + (n === 1 ? uno : varios); }

  function corto(nombre) {
    var partes = String(nombre).split('·');
    var txt = partes[partes.length - 1].trim();
    return txt.length > 24 ? txt.slice(0, 23) + '…' : txt;
  }

  /* ------------------------------------------------------------ proyección
     Equirrectangular con la longitud corregida por el coseno de la latitud:
     a esta escala (unos kilómetros) es indistinguible de una proyección
     de verdad, y no necesita ninguna biblioteca. */
  function encuadre(puntos) {
    var lats = puntos.map(function (p) { return p.lat; });
    var lngs = puntos.map(function (p) { return p.lng; });
    var latMin = Math.min.apply(null, lats), latMax = Math.max.apply(null, lats);
    var lngMin = Math.min.apply(null, lngs), lngMax = Math.max.apply(null, lngs);
    var latC = (latMin + latMax) / 2, lngC = (lngMin + lngMax) / 2;
    var kx = Math.cos(latC * Math.PI / 180);
    // Al menos unos 4 km de lado, para que se vea el entorno y no solo
    // los círculos; y un margen para que ninguno quede pegado al borde.
    var w = Math.max((lngMax - lngMin) * kx * 1.5, 0.036);
    var alto = Math.max((latMax - latMin) * 1.5, 0.036);
    if (w / alto < ANCHO / ALTO) w = alto * ANCHO / ALTO; else alto = w * ALTO / ANCHO;
    var escala = ANCHO / w;
    var x0 = lngC * kx - w / 2, y0 = latC + alto / 2;
    return {
      x: function (lng) { return (lng * kx - x0) * escala; },
      y: function (lat) { return (y0 - lat) * escala; },
      kmEnPx: escala / 111.32,
      lat: [y0 - alto, y0], lng: [x0 / kx, (x0 + w) / kx]
    };
  }

  function cruzaSerena(caja) {
    var s = SERENA.caja;
    return caja.lat[0] < s.latMax && caja.lat[1] > s.latMin && caja.lng[0] < s.lngMax && caja.lng[1] > s.lngMin;
  }

  function linea(puntos, p) {
    return puntos.map(function (q, i) {
      return (i ? 'L' : 'M') + p.x(q[1]).toFixed(1) + ' ' + p.y(q[0]).toFixed(1);
    }).join(' ');
  }

  /* ------------------------------------------------------------ el dibujo */

  var svg, seleccionado = null, nodos = {};

  function radio(t) {
    return t.medida > 0 ? Math.min(30, 11 + 4.3 * Math.sqrt(t.medida)) : 9;
  }

  function dibujar() {
    if (!ubicados.length) return;
    lienzo.textContent = '';
    nodos = {};
    medir();
    var p = encuadre(ubicados);

    svg = el('svg', {
      viewBox: '0 0 ' + ANCHO + ' ' + ALTO, class: 'mapa-svg', role: 'group',
      'aria-label': 'Mapa de ' + plural(ubicados.length, 'territorio ubicado', 'territorios ubicados') +
        '. Cada círculo se puede elegir con el teclado.'
    }, lienzo);

    el('rect', { x: 0, y: 0, width: ANCHO, height: ALTO, class: 'mp-tierra' }, svg);

    if (cruzaSerena(p)) {
      var mar = linea(SERENA.costa, p) + ' L -2000 ' + p.y(SERENA.costa[SERENA.costa.length - 1][0]).toFixed(1) +
        ' L -2000 ' + p.y(SERENA.costa[0][0]).toFixed(1) + ' Z';
      el('path', { d: mar, class: 'mp-mar' }, svg);
      el('path', { d: linea(SERENA.costa, p), class: 'mp-costa' }, svg);
      el('path', { d: linea(SERENA.rio, p), class: 'mp-rio' }, svg);

      // Rótulos del fondo, solo si caen dentro del cuadro.
      var xMar = p.x(-71.300), yMar = p.y(-29.935);
      if (xMar > 40) {
        var tMar = el('text', { x: Math.min(xMar, ANCHO * 0.3) - 12, y: Math.max(40, Math.min(yMar, ALTO - 40)), class: 'mp-rot mp-rot-mar', 'text-anchor': 'end' }, svg);
        tMar.textContent = 'Océano Pacífico';
      }
      var rio = SERENA.rio[5];
      var xr = p.x(rio[1]), yr = p.y(rio[0]);
      if (xr > 20 && xr < ANCHO - 80 && yr > 20 && yr < ALTO - 20) {
        var tRio = el('text', { x: xr, y: yr + 18, class: 'mp-rot mp-rot-rio' }, svg);
        tRio.textContent = 'Río Elqui';
      }
      SERENA.lugares.forEach(function (l) {
        var x = p.x(l.lng), y = p.y(l.lat);
        if (x < 10 || x > ANCHO - 10 || y < 10 || y > ALTO - 10) return;
        el('rect', { x: x - 3.5, y: y - 3.5, width: 7, height: 7, class: 'mp-lugar', transform: 'rotate(45 ' + x + ' ' + y + ')' }, svg);
        var t = el('text', { x: x + 9, y: y + 4, class: 'mp-rot mp-rot-lugar' }, svg);
        t.textContent = l.nombre;
      });
    }

    escalaGrafica(p);

    // Los más grandes primero, para que uno chico no quede tapado.
    var orden = ubicados.slice().sort(function (a, b) { return radio(b) - radio(a); })
      .map(function (t) { return { t: t, x: p.x(t.lng), y: p.y(t.lat), r: radio(t) }; });
    var ocupados = orden.map(function (b) {
      return { x1: b.x - b.r, x2: b.x + b.r, y1: b.y - b.r, y2: b.y + b.r };
    });
    var capa = el('g', { class: 'mp-territorios' }, svg);
    orden.forEach(function (b) { nodos[b.t.id] = burbuja(b, capa); });
    orden.forEach(function (b) { rotular(b, nodos[b.t.id], ocupados); });
    if (seleccionado !== null && nodos[seleccionado]) nodos[seleccionado].classList.add('sel');
  }

  /* El nombre va a la derecha del círculo; si choca con otro círculo u otro
     nombre, prueba a la izquierda, abajo y arriba, en ese orden. */
  function rotular(b, g, ocupados) {
    var texto = corto(b.t.nombre);
    var w = texto.length * 7 + 4, x = b.x, y = b.y, r = b.r;
    var opciones = [
      { x: x + r + 10, y: y + 4.5, a: 'start', c: { x1: x + r + 8, x2: x + r + 10 + w, y1: y - 9, y2: y + 8 } },
      { x: x - r - 10, y: y + 4.5, a: 'end', c: { x1: x - r - 10 - w, x2: x - r - 8, y1: y - 9, y2: y + 8 } },
      { x: x, y: y + r + 20, a: 'middle', c: { x1: x - w / 2, x2: x + w / 2, y1: y + r + 7, y2: y + r + 24 } },
      { x: x, y: y - r - 12, a: 'middle', c: { x1: x - w / 2, x2: x + w / 2, y1: y - r - 26, y2: y - r - 9 } }
    ];
    function cabe(o) {
      if (o.c.x1 < 4 || o.c.x2 > ANCHO - 4 || o.c.y1 < 4 || o.c.y2 > ALTO - 4) return false;
      return !ocupados.some(function (q) {
        return !(o.c.x2 < q.x1 || o.c.x1 > q.x2 || o.c.y2 < q.y1 || o.c.y1 > q.y2);
      });
    }
    var elegida = opciones.filter(cabe)[0] || opciones.filter(function (o) {
      return o.c.x1 >= 4 && o.c.x2 <= ANCHO - 4;
    })[0] || opciones[0];
    ocupados.push(elegida.c);
    var rot = el('text', { x: elegida.x, y: elegida.y, 'text-anchor': elegida.a, class: 'mp-rot mp-rot-t' }, g);
    rot.textContent = texto;
  }

  function escalaGrafica(p) {
    var km = p.kmEnPx > 140 ? 0.5 : (p.kmEnPx > 70 ? 1 : 2);
    var largo = km * p.kmEnPx;
    var g = el('g', { class: 'mp-escala', transform: 'translate(' + (ANCHO - largo - 24) + ' ' + (ALTO - 26) + ')' }, svg);
    el('path', { d: 'M0 -5 V0 H' + largo.toFixed(1) + ' V-5' }, g);
    var t = el('text', { x: largo / 2, y: -9, 'text-anchor': 'middle' }, g);
    t.textContent = (km < 1 ? '500 m' : km + ' km') + ' aprox.';
  }

  function burbuja(b, capa) {
    var t = b.t, x = b.x, y = b.y, r = b.r;
    var g = el('g', {
      class: 'mp-t mp-' + t.semaforo + (t.medida ? '' : ' mp-cero'),
      tabindex: '0', role: 'button', 'aria-pressed': 'false',
      'data-territorio': t.id,
      'aria-label': t.nombre + '. ' + t.semaforo_texto + ': ' + t.hace.toLowerCase() +
        '. ' + plural(t.medida, 'actividad', 'actividades') + ' en el trimestre.'
    }, capa);
    el('title', {}, g).textContent = t.nombre + ' · ' + t.hace;
    el('circle', { cx: x, cy: y, r: r + 6, class: 'mp-anillo' }, g);
    el('circle', { cx: x, cy: y, r: r, class: 'mp-punto' }, g);
    if (t.medida > 0) {
      var n = el('text', { x: x, y: y + 4.5, 'text-anchor': 'middle', class: 'mp-num' }, g);
      n.textContent = t.medida;
    }

    g.addEventListener('click', function () { elegir(t.id, { desdeMapa: true }); });
    g.addEventListener('keydown', function (ev) {
      if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); elegir(t.id, { desdeMapa: true }); }
      if (ev.key === 'Escape') { volver(); }
    });
    return g;
  }

  /* ------------------------------------------------------------ el panel */

  var inicio = document.getElementById('mapa-panel-inicio');

  function fila(dl, termino, valor, clase) {
    var d = h('div', 'mp-par' + (clase ? ' ' + clase : ''));
    d.appendChild(h('dt', '', termino));
    var dd = h('dd');
    if (valor instanceof Node) dd.appendChild(valor); else dd.textContent = valor;
    d.appendChild(dd);
    dl.appendChild(d);
  }

  function cifra(padre, numero, rotulo, nota, clase) {
    var c = h('div', 'mp-cifra' + (clase ? ' ' + clase : ''));
    c.appendChild(h('span', 'n', String(numero)));
    c.appendChild(h('span', 'r', rotulo));
    if (nota) c.appendChild(h('span', 'nota', nota));
    padre.appendChild(c);
  }

  var CHIP = { verde: 'ok', ambar: 'warn', rojo: 'bad', gris: 'off' };

  function detalle(t) {
    var caja = h('div', 'mapa-detalle');

    var volverBtn = h('button', 'btn btn-ghost btn-sm mp-volver', 'Volver a la lista');
    volverBtn.type = 'button';
    volverBtn.addEventListener('click', volver);
    caja.appendChild(volverBtn);

    caja.appendChild(h('span', 'chip ' + CHIP[t.semaforo], t.semaforo_texto));
    var titulo = h('h3', 'mp-titulo', t.nombre);
    titulo.tabIndex = -1;
    caja.appendChild(titulo);
    caja.appendChild(h('p', 'mp-sub', t.delegacion + ' · ' + t.codigo + (t.activo ? '' : ' · desactivado')));

    var dl = h('dl', 'mp-datos');
    fila(dl, 'Última presencia', t.ultima ? t.ultima + ' (' + t.hace.toLowerCase() + ')' : 'Ninguna registrada');
    if (datos.modo === 'personal') fila(dl, 'Se cuenta', 'Solo tus actividades');
    caja.appendChild(dl);

    var cifras = h('div', 'mp-cifras');
    cifra(cifras, t.registradas, plural(t.registradas, 'actividad', 'actividades').replace(/^\d+ /, ''),
      plural(t.verificadas, 'verificada', 'verificadas'));
    cifra(cifras, t.abiertos, t.abiertos === 1 ? 'compromiso abierto' : 'compromisos abiertos',
      t.vencidos ? plural(t.vencidos, 'vencido', 'vencidos') : 'ninguno vencido', t.vencidos ? 'mp-alerta' : '');
    cifra(cifras, t.gestiones, t.gestiones === 1 ? 'gestión social' : 'gestiones sociales', 'en el trimestre');
    caja.appendChild(cifras);

    // Lo que se puede hacer va justo después del estado: es para lo que se
    // abre el panel. El detalle de abajo es para quien quiere más contexto.
    if (t.acciones.length) {
      var acc = h('div', 'mp-acciones');
      t.acciones.forEach(function (a) {
        var link = h('a', 'btn ' + (a.principal ? 'btn-primary' : 'btn-secondary') + ' btn-sm', a.texto);
        link.href = a.url;
        acc.appendChild(link);
      });
      caja.appendChild(acc);
    }

    if (t.por_tipo.length) {
      caja.appendChild(h('h4', '', 'Qué se hizo'));
      var max = Math.max.apply(null, t.por_tipo.map(function (x) { return x[1]; }));
      var lista = h('ul', 'mp-tipos');
      t.por_tipo.forEach(function (x) {
        var li = h('li');
        li.appendChild(h('span', 'et', x[0]));
        var barra = h('span', 'bar');
        var lleno = h('i');
        lleno.style.width = Math.max(6, Math.round(100 * x[1] / max)) + '%';
        barra.appendChild(lleno);
        li.appendChild(barra);
        li.appendChild(h('span', 'n', String(x[1])));
        lista.appendChild(li);
      });
      caja.appendChild(lista);
    }

    if (t.juntas.length) {
      caja.appendChild(h('h4', '', t.juntas.length === 1 ? 'Junta de vecinos' : 'Juntas de vecinos'));
      var ul = h('ul', 'mp-juntas');
      t.juntas.forEach(function (j) {
        var li = h('li');
        li.appendChild(h('b', '', j.nombre));
        li.appendChild(h('span', '', plural(j.socios, 'socio vigente', 'socios vigentes') + ' · ' +
          (j.contacto ? 'último contacto el ' + j.contacto : 'sin contacto registrado')));
        ul.appendChild(li);
      });
      caja.appendChild(ul);
    }

    if (t.hitos) {
      caja.appendChild(h('p', 'mp-nota', plural(t.hitos, 'hito planificado', 'hitos planificados') + ' en este territorio durante el trimestre.'));
    }

    if (t.quienes.length) {
      caja.appendChild(h('h4', '', 'Quiénes fueron'));
      var q = h('ul', 'mp-quienes');
      t.quienes.forEach(function (x) {
        var li = h('li');
        li.appendChild(h('span', '', x.nombre));
        li.appendChild(h('span', 'n', plural(x.n, 'actividad', 'actividades')));
        q.appendChild(li);
      });
      caja.appendChild(q);
    }

    return caja;
  }

  function marcarFila(id) {
    document.querySelectorAll('[data-territorio-fila]').forEach(function (tr) {
      tr.classList.toggle('sel', String(tr.getAttribute('data-territorio-fila')) === String(id));
    });
  }

  function elegir(id, op) {
    var t = porId[id];
    if (!t) return;
    op = op || {};
    seleccionado = id;
    Object.keys(nodos).forEach(function (k) {
      var activo = String(k) === String(id);
      nodos[k].classList.toggle('sel', activo);
      nodos[k].setAttribute('aria-pressed', activo ? 'true' : 'false');
    });
    // El elegido va al frente, para que su anillo no quede debajo de otro.
    if (nodos[id] && nodos[id].parentNode) nodos[id].parentNode.appendChild(nodos[id]);

    panel.textContent = '';
    panel.appendChild(detalle(t));
    marcarFila(id);
    try { history.replaceState(null, '', '#t-' + id); } catch (e) { /* sin historial */ }

    if (!op.desdeMapa) {
      var destino = nodos[id] ? lienzo : panel;
      destino.scrollIntoView({ behavior: reducir ? 'auto' : 'smooth', block: 'center' });
    }
    if (op.desdeMapa && nodos[id]) nodos[id].focus();
    else {
      var titulo = panel.querySelector('.mp-titulo');
      if (titulo) titulo.focus({ preventScroll: true });
    }
  }

  function volver() {
    var anterior = seleccionado;
    seleccionado = null;
    Object.keys(nodos).forEach(function (k) {
      nodos[k].classList.remove('sel');
      nodos[k].setAttribute('aria-pressed', 'false');
    });
    marcarFila(null);
    panel.textContent = '';
    if (inicio) panel.appendChild(inicio);
    try { history.replaceState(null, '', location.pathname + location.search); } catch (e) { /* nada */ }
    if (anterior !== null && nodos[anterior]) nodos[anterior].focus();
  }

  /* ------------------------------------------------------------ arranque */

  dibujar();

  var anchoDibujado = ANCHO, espera = null;
  window.addEventListener('resize', function () {
    clearTimeout(espera);
    espera = setTimeout(function () {
      if (Math.abs((lienzo.clientWidth || 0) - anchoDibujado) < 8) return;
      dibujar();
      anchoDibujado = ANCHO;
      if (seleccionado !== null && nodos[seleccionado]) {
        nodos[seleccionado].setAttribute('aria-pressed', 'true');
        nodos[seleccionado].parentNode.appendChild(nodos[seleccionado]);
      }
    }, 150);
  });

  document.addEventListener('click', function (ev) {
    var disparador = ev.target.closest('[data-territorio]');
    if (!disparador || disparador.closest('svg')) return;
    ev.preventDefault();
    elegir(Number(disparador.getAttribute('data-territorio')));
  });

  // Los filtros se aplican al cambiarlos; el botón queda para quien no
  // tiene JavaScript.
  var filtros = document.querySelector('form[data-autoenvio]');
  if (filtros) {
    filtros.addEventListener('change', function () { filtros.submit(); });
  }

  var marca = /^#t-(\d+)$/.exec(location.hash);
  if (marca && porId[Number(marca[1])]) elegir(Number(marca[1]), { desdeMapa: false });
})();

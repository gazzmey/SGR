/* SGR · mapa de presencia territorial.

   Dibuja el mapa con SVG propio, sin servicios de mapas externos: no hay
   teselas que descargar ni claves que configurar, y funciona en cualquier
   red, también en la del municipio. Los datos son los mismos de la tabla
   que el servidor escribe debajo (gestion/mapa.py), así que si este archivo
   no carga no se pierde nada.

   Qué hay en el mapa
     · un punto por territorio ubicado, en el centro aproximado que se
       escribió en su ficha; el color es el semáforo de la última presencia y
       el tamaño, las actividades del trimestre;
     · alrededor de cada punto, su zona: una mancha del mismo color que se
       desvanece hacia afuera y se reparte el espacio con las vecinas. No es
       el límite oficial del territorio: muestra de un vistazo qué parte de
       la ciudad lleva tiempo sin presencia;
     · de fondo, cuando los territorios están en La Serena, una referencia
       aproximada de la costa, el río Elqui, la Ruta 5 y dos hitos para
       orientarse. No es cartografía: es un croquis.

   Se puede mover arrastrando, acercar con los botones, con Ctrl + rueda o
   con dos dedos, y recorrer con el teclado. No hay casas ni direcciones: el
   mapa no recibe ninguna.

   Además del semáforo, el mapa hace tres cosas:
     · «Cambio vs. trimestre anterior»: pinta cada territorio según si tuvo
       más o menos actividades que el trimestre pasado a la misma altura;
     · «Armar una salida»: se tocan los territorios a visitar, el orden se
       arma por cercanía y se pasa a la hoja de ruta (gestion/salida.html);
     · ubicar un territorio con un clic, para quien puede editar territorios:
       se guarda con la misma validación que la ficha. */
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
  var reducir = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  var porId = {};
  datos.territorios.forEach(function (t) { porId[t.id] = t; });
  var ubicados = datos.territorios.filter(function (t) { return t.lat !== null && t.lng !== null; });
  var orden = datos.territorios.map(function (t) { return t.id; });

  /* ---------------------------------------------- referencia de La Serena
     Puntos aproximados (latitud, longitud). La costa va de sur a norte; el
     río, de la desembocadura hacia el valle; la Ruta 5, de sur a norte.
     Basta para orientarse; no sirve para medir. */
  var SERENA = {
    caja: { latMin: -30.05, latMax: -29.70, lngMin: -71.42, lngMax: -71.05 },
    costa: [
      [-30.200, -71.420], [-29.985, -71.365], [-29.962, -71.348], [-29.952, -71.336],
      [-29.947, -71.318], [-29.943, -71.302], [-29.935, -71.292], [-29.924, -71.284],
      [-29.913, -71.278], [-29.905, -71.2750], [-29.896, -71.2745], [-29.887, -71.276],
      [-29.876, -71.279], [-29.862, -71.283], [-29.845, -71.287], [-29.828, -71.291],
      [-29.810, -71.296], [-29.790, -71.300], [-29.600, -71.330]
    ],
    rio: [
      [-29.8870, -71.2765], [-29.8885, -71.2660], [-29.8900, -71.2560], [-29.8915, -71.2460],
      [-29.8930, -71.2360], [-29.8945, -71.2260], [-29.8960, -71.2160], [-29.8980, -71.2050],
      [-29.9010, -71.1930], [-29.9040, -71.1800], [-29.9070, -71.1650], [-29.9100, -71.1500],
      [-29.9130, -71.1300], [-29.9170, -71.1000]
    ],
    ruta5: [
      [-29.990, -71.330], [-29.955, -71.300], [-29.940, -71.284], [-29.925, -71.271],
      [-29.912, -71.263], [-29.900, -71.2595], [-29.890, -71.2590], [-29.875, -71.2610],
      [-29.858, -71.2650], [-29.835, -71.2700], [-29.800, -71.2780], [-29.700, -71.2950]
    ],
    avenida: [[-29.9058, -71.2735], [-29.9050, -71.2650], [-29.9042, -71.2580], [-29.9035, -71.2520]],
    lugares: [
      { nombre: 'Plaza de Armas', lat: -29.9027, lng: -71.2519 },
      { nombre: 'Faro Monumental', lat: -29.9058, lng: -71.2742, faro: true }
    ]
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

  function icono(d, tam) {
    var s = el('svg', { width: tam || 16, height: tam || 16, viewBox: '0 0 24 24', fill: 'none',
      stroke: 'currentColor', 'stroke-width': '2', 'stroke-linecap': 'round',
      'stroke-linejoin': 'round', 'aria-hidden': 'true', class: 'i' });
    el('path', { d: d }, s);
    return s;
  }
  var IC = {
    atras: 'M14.5 6 8.5 12l6 6',
    adelante: 'm9.5 6 6 6-6 6',
    mas: 'M12 5.5v13M5.5 12h13',
    menos: 'M5.5 12h13',
    encuadrar: 'M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5'
  };

  function plural(n, uno, varios) { return n + ' ' + (n === 1 ? uno : varios); }

  function corto(nombre) {
    var partes = String(nombre).split('·');
    var txt = partes[partes.length - 1].trim();
    return txt.length > 24 ? txt.slice(0, 23) + '…' : txt;
  }

  function limitar(v, a, b) { return Math.max(a, Math.min(b, v)); }

  /* Una curva suave que pasa por todos los puntos (Catmull-Rom convertida a
     Bézier): la costa y el río dejan de verse como una línea quebrada. */
  function curva(pts) {
    if (pts.length < 2) return '';
    var d = 'M' + pts[0][0].toFixed(1) + ' ' + pts[0][1].toFixed(1);
    for (var i = 0; i < pts.length - 1; i++) {
      var p0 = pts[i - 1] || pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] || p2;
      d += ' C' + (p1[0] + (p2[0] - p0[0]) / 6).toFixed(1) + ' ' + (p1[1] + (p2[1] - p0[1]) / 6).toFixed(1) +
        ' ' + (p2[0] - (p3[0] - p1[0]) / 6).toFixed(1) + ' ' + (p2[1] - (p3[1] - p1[1]) / 6).toFixed(1) +
        ' ' + p2[0].toFixed(1) + ' ' + p2[1].toFixed(1);
    }
    return d;
  }

  /* La misma línea corrida hacia un lado (hacia el mar, en la costa). */
  function desplazar(pts, distancia) {
    return pts.map(function (p, i) {
      var a = pts[i - 1] || p, b = pts[i + 1] || p;
      var dx = b[0] - a[0], dy = b[1] - a[1], largo = Math.sqrt(dx * dx + dy * dy) || 1;
      return [p[0] + dy / largo * distancia, p[1] - dx / largo * distancia];
    });
  }

  /* Recorta un polígono convexo con el semiplano de los puntos más cerca de
     «a» que de «b» (Sutherland-Hodgman con una sola arista). Repetido con
     cada vecino da la celda de Voronoi de «a». */
  function recortar(poligono, a, b) {
    var mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2, nx = b[0] - a[0], ny = b[1] - a[1];
    function lado(p) { return (p[0] - mx) * nx + (p[1] - my) * ny; }
    var salida = [];
    for (var i = 0; i < poligono.length; i++) {
      var p = poligono[i], q = poligono[(i + 1) % poligono.length];
      var lp = lado(p), lq = lado(q);
      if (lp <= 0) salida.push(p);
      if ((lp < 0 && lq > 0) || (lp > 0 && lq < 0)) {
        var t = lp / (lp - lq);
        salida.push([p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t]);
      }
    }
    return salida;
  }

  /* ------------------------------------------------------------ la vista
     Proyección equirrectangular con la longitud corregida por el coseno de
     la latitud: a esta escala (unos kilómetros) es indistinguible de una
     proyección de verdad. La vista es un centro y una escala; mover y
     acercar solo cambia esos tres números y se vuelve a dibujar. */
  var ANCHO = 800, ALTO = 600, kx = 1, base = null, vista = null;

  function medir() {
    ANCHO = Math.max(300, Math.round(lienzo.clientWidth || 800));
    ALTO = ANCHO < 640 ? Math.round(Math.max(340, ANCHO * 1.0)) : 600;
  }

  function encuadrar() {
    if (!ubicados.length) {
      // Nada ubicado todavía: el centro de La Serena, con unos 7 km de lado.
      kx = Math.cos(-29.905 * Math.PI / 180);
      base = { cx: -71.252 * kx, cy: -29.895, escala: Math.min(ANCHO, ALTO) / 0.065 };
      return;
    }
    var lats = ubicados.map(function (t) { return t.lat; });
    var lngs = ubicados.map(function (t) { return t.lng; });
    var latMin = Math.min.apply(null, lats), latMax = Math.max.apply(null, lats);
    var lngMin = Math.min.apply(null, lngs), lngMax = Math.max.apply(null, lngs);
    var latC = (latMin + latMax) / 2, lngC = (lngMin + lngMax) / 2;
    kx = Math.cos(latC * Math.PI / 180);
    // Al menos unos 4 km de lado, para que se vea el entorno; y margen para
    // que ningún punto quede pegado al borde ni debajo de la leyenda.
    var w = Math.max((lngMax - lngMin) * kx * 1.6, 0.038);
    var alto = Math.max((latMax - latMin) * 1.6, 0.038);
    var escala = Math.min(ANCHO / w, ALTO / alto);
    base = { cx: lngC * kx, cy: latC, escala: escala };
  }

  function X(lng) { return (lng * kx - vista.cx) * vista.escala + ANCHO / 2; }
  function Y(lat) { return (vista.cy - lat) * vista.escala + ALTO / 2; }
  function kmEnPx() { return vista.escala / 111.32; }
  function aPantalla(lista) { return lista.map(function (q) { return [X(q[1]), Y(q[0])]; }); }

  function enSerena() {
    var s = SERENA.caja;
    var latN = vista.cy + ALTO / 2 / vista.escala, latS = vista.cy - ALTO / 2 / vista.escala;
    var lngO = (vista.cx - ANCHO / 2 / vista.escala) / kx, lngE = (vista.cx + ANCHO / 2 / vista.escala) / kx;
    return latS < s.latMax && latN > s.latMin && lngO < s.lngMax && lngE > s.lngMin;
  }

  /* ------------------------------------------------------------ el dibujo */

  var svg, mundo, capaDinamica, leyenda, seleccionado = null, nodos = {}, zonas = {};

  /* Lo que pinta el mapa. «presencia» es el semáforo; «cambio» compara
     con el trimestre anterior a la misma altura. */
  var comparacion = datos.comparacion;
  var capa = (comparacion && /[?&]ver=cambio(&|$)/.test(location.search)) ? 'cambio' : 'presencia';

  /* Lo que se está haciendo: mirar (null), armar una salida o ubicar. */
  var modo = null;
  var ruta = [], ordenManual = false;
  var ubicando = null;
  var MAXIMO_PARADAS = 12;

  function cambioDe(t) { return t.anterior === null ? 0 : t.medida - t.anterior; }
  function magnitud(t) { return capa === 'cambio' ? Math.abs(cambioDe(t)) : t.medida; }
  function colorDe(t) {
    if (capa !== 'cambio') return t.semaforo;
    var c = cambioDe(t);
    return c > 0 ? 'verde' : (c < 0 ? 'rojo' : 'gris');
  }
  function cifraDe(t) {
    if (capa !== 'cambio') return t.medida > 0 ? String(t.medida) : '';
    var c = cambioDe(t);
    return c > 0 ? '+' + c : (c < 0 ? '−' + (-c) : '');
  }
  function radio(t) {
    var n = magnitud(t);
    return n > 0 ? Math.min(26, 10 + 3.8 * Math.sqrt(n)) : 8;
  }
  function textoCambio(t) {
    if (t.anterior === null) return '';
    var c = cambioDe(t);
    if (c === 0) return 'igual que el trimestre anterior (' + t.anterior + ')';
    return Math.abs(c) + (c > 0 ? ' más' : ' menos') + ' que el trimestre anterior (' + t.anterior + ')';
  }

  function preparar() {
    lienzo.textContent = '';
    svg = el('svg', {
      class: 'mapa-svg', role: 'group',
      'aria-label': 'Mapa de ' + plural(ubicados.length, 'territorio ubicado', 'territorios ubicados') +
        '. Cada punto se puede elegir con el teclado.'
    }, lienzo);

    var defs = el('defs', {}, svg);
    var colores = { verde: '#2E8A57', ambar: '#D08A10', rojo: '#C14A2E', gris: '#A89E99' };
    Object.keys(colores).forEach(function (k) {
      var g = el('radialGradient', { id: 'mp-zona-' + k }, defs);
      el('stop', { offset: '0', 'stop-color': colores[k], 'stop-opacity': '.55' }, g);
      el('stop', { offset: '.45', 'stop-color': colores[k], 'stop-opacity': '.32' }, g);
      el('stop', { offset: '1', 'stop-color': colores[k], 'stop-opacity': '0' }, g);
    });
    var mar = el('linearGradient', { id: 'mp-mar', x1: '1', y1: '0', x2: '0', y2: '0' }, defs);
    el('stop', { offset: '0', 'stop-color': '#D6E5EA' }, mar);
    el('stop', { offset: '1', 'stop-color': '#BCD2DA' }, mar);
    var sombra = el('filter', { id: 'mp-sombra', x: '-50%', y: '-50%', width: '200%', height: '200%' }, defs);
    el('feDropShadow', { dx: '0', dy: '1.5', stdDeviation: '1.6', 'flood-color': '#1E1715', 'flood-opacity': '.28' }, sombra);
    // El borde entre dos zonas vecinas se difumina: son zonas aproximadas y
    // no deben parecer límites trazados.
    var difuso = el('filter', { id: 'mp-difuso', x: '-20%', y: '-20%', width: '140%', height: '140%' }, defs);
    el('feGaussianBlur', { stdDeviation: '7' }, difuso);
    capaDinamica = el('defs', {}, svg);

    mundo = el('g', { class: 'mp-mundo' }, svg);

    // Los controles y la leyenda son HTML encima del dibujo: se leen y se
    // tocan mejor que si fueran parte del SVG.
    var controles = h('div', 'mp-controles');
    [['Acercar', IC.mas, function () { zoom(1.6); }],
     ['Alejar', IC.menos, function () { zoom(1 / 1.6); }],
     ['Ver todos los territorios', IC.encuadrar, function () { irA(base); }]].forEach(function (c) {
      var b = h('button', 'mp-boton');
      b.type = 'button';
      b.title = c[0];
      b.setAttribute('aria-label', c[0]);
      b.appendChild(icono(c[1], 18));
      b.addEventListener('click', c[2]);
      controles.appendChild(b);
    });
    lienzo.appendChild(controles);

    leyenda = h('div', 'mp-leyenda');
    leyenda.setAttribute('aria-hidden', 'true');
    lienzo.appendChild(leyenda);
    pintarLeyenda();

    tip = h('div', 'mp-tip');
    tip.setAttribute('aria-hidden', 'true');
    lienzo.appendChild(tip);

    aviso = h('div', 'mp-aviso', 'Mantén Ctrl y usa la rueda para acercar el mapa');
    aviso.setAttribute('aria-hidden', 'true');
    lienzo.appendChild(aviso);

    franja = h('div', 'mp-franja');
    franja.setAttribute('role', 'status');
    lienzo.appendChild(franja);

    escuchar();
  }

  function pintarLeyenda() {
    leyenda.textContent = '';
    var filas;
    if (capa === 'cambio') {
      filas = [['verde', 'Más actividades que antes'], ['rojo', 'Menos que antes'], ['hueco gris', 'Igual que antes']];
    } else {
      filas = [['verde', 'Hasta ' + datos.umbral.verde + ' días'],
               ['ambar', (datos.umbral.verde + 1) + ' a ' + datos.umbral.ambar + ' días'],
               ['rojo', 'Más de ' + datos.umbral.ambar + ' o nunca']];
      if (ubicados.some(function (t) { return t.semaforo === 'gris'; })) filas.push(['gris', 'Territorio desactivado']);
      filas.push(['hueco', 'Nadie fue en el trimestre']);
    }
    filas.forEach(function (x) {
      var fila = h('span', 'mp-ley-fila');
      fila.appendChild(h('i', 'mp-ley-punto ' + x[0]));
      fila.appendChild(document.createTextNode(x[1]));
      leyenda.appendChild(fila);
    });
    leyenda.appendChild(h('span', 'mp-ley-nota', capa === 'cambio'
      ? 'Se compara con ' + comparacion.texto + '. Más grande, más diferencia.'
      : 'Más grande, más actividades del trimestre (' + (datos.presencia_texto || 'todo lo registrado') +
        '). La mancha es una zona aproximada.'));
  }

  function dibujar() {
    if (!svg) return;
    svg.setAttribute('viewBox', '0 0 ' + ANCHO + ' ' + ALTO);
    svg.setAttribute('width', ANCHO);
    svg.setAttribute('height', ALTO);
    svg.classList.toggle('mp-armando', modo === 'salida');
    svg.classList.toggle('mp-ubicando', modo === 'ubicar');
    mundo.removeAttribute('transform');
    mundo.textContent = '';
    capaDinamica.textContent = '';
    nodos = {};
    zonas = {};

    var delFondo = fondo();

    // Mientras se corrige la ubicación de un territorio, su punto se ve en
    // el lugar nuevo y el viejo queda como un fantasma.
    var puntos = ubicados.filter(function (t) {
      return !(modo === 'ubicar' && ubicando && ubicando.id === t.id && ubicando.lat !== null);
    }).map(function (t) {
      return { t: t, x: X(t.lng), y: Y(t.lat), r: radio(t) };
    });

    // Las zonas: celdas de Voronoi con una mancha que se desvanece.
    var capaZonas = el('g', { class: 'mp-zonas', filter: 'url(#mp-difuso)' }, mundo);
    var alcance = limitar(kmEnPx() * 1.35, 44, 260);
    var mayor = Math.max.apply(null, [1].concat(puntos.map(function (p) { return magnitud(p.t); })));
    var margen = 400;
    var caja = [[-margen, -margen], [ANCHO + margen, -margen], [ANCHO + margen, ALTO + margen], [-margen, ALTO + margen]];
    puntos.forEach(function (a, i) {
      var celda = caja;
      puntos.forEach(function (b, j) {
        if (i === j || celda.length < 3) return;
        if (Math.abs(a.x - b.x) + Math.abs(a.y - b.y) < 0.5) return;
        if (Math.abs(a.x - b.x) > alcance * 2.2 || Math.abs(a.y - b.y) > alcance * 2.2) return;
        celda = recortar(celda, [a.x, a.y], [b.x, b.y]);
      });
      if (celda.length < 3) return;
      var id = 'mp-celda-' + a.t.id;
      var clip = el('clipPath', { id: id }, capaDinamica);
      el('polygon', { points: celda.map(function (p) { return p[0].toFixed(1) + ',' + p[1].toFixed(1); }).join(' ') }, clip);
      var atributos = {
        cx: a.x.toFixed(1), cy: a.y.toFixed(1), r: alcance.toFixed(1),
        fill: 'url(#mp-zona-' + colorDe(a.t) + ')', 'clip-path': 'url(#' + id + ')',
        class: 'mp-zona' + (a.t.id === seleccionado ? ' sel' : '')
      };
      // En «cambio», la mancha es más intensa cuanto mayor la diferencia.
      if (capa === 'cambio') atributos.style = 'fill-opacity:' + (0.35 + 0.65 * magnitud(a.t) / mayor).toFixed(2);
      zonas[a.t.id] = el('circle', atributos, capaZonas);
    });

    // Los puntos: los más grandes primero, para que uno chico no quede tapado.
    puntos.sort(function (a, b) { return b.r - a.r; });
    var ocupados = puntos.map(function (b) {
      return { x1: b.x - b.r - 2, x2: b.x + b.r + 2, y1: b.y - b.r - 2, y2: b.y + b.r + 2 };
    }).concat(delFondo);
    rotulosDeDelegacion(puntos, ocupados);
    dibujarRuta(puntos);
    var capaPuntos = el('g', { class: 'mp-territorios' }, mundo);
    puntos.forEach(function (b) { nodos[b.t.id] = punto(b, capaPuntos); });
    puntos.forEach(function (b) { rotular(b, nodos[b.t.id], ocupados); });
    numerosDeRuta(puntos, capaPuntos);
    dibujarUbicando(capaPuntos);

    svg.classList.toggle('mp-con-sel', seleccionado !== null && !!nodos[seleccionado]);
    if (seleccionado !== null && nodos[seleccionado]) {
      nodos[seleccionado].classList.add('sel');
      nodos[seleccionado].setAttribute('aria-pressed', 'true');
      capaPuntos.appendChild(nodos[seleccionado]);
    }
    escala();
  }

  /* La salida a terreno: una línea punteada que une las paradas en orden. */
  function dibujarRuta(puntos) {
    if (modo !== 'salida' || ruta.length < 2) return;
    var donde = {};
    puntos.forEach(function (p) { donde[p.t.id] = p; });
    var pts = ruta.map(function (id) { return donde[id]; }).filter(Boolean).map(function (p) { return [p.x, p.y]; });
    if (pts.length < 2) return;
    var d = 'M' + pts.map(function (p) { return p[0].toFixed(1) + ' ' + p[1].toFixed(1); }).join(' L');
    el('path', { d: d, class: 'mp-recorrido-borde' }, mundo);
    el('path', { d: d, class: 'mp-recorrido' }, mundo);
  }

  function numerosDeRuta(puntos, capaPuntos) {
    if (modo !== 'salida') return;
    puntos.forEach(function (p) {
      var i = ruta.indexOf(p.t.id);
      if (i < 0) { nodos[p.t.id].classList.add('mp-fuera'); return; }
      nodos[p.t.id].classList.add('mp-en-ruta');
      var g = el('g', { class: 'mp-parada', transform: 'translate(' + (p.x + p.r * 0.72).toFixed(1) + ' ' + (p.y - p.r * 0.72).toFixed(1) + ')' }, capaPuntos);
      el('circle', { r: 10 }, g);
      el('text', { y: 4, 'text-anchor': 'middle' }, g).textContent = i + 1;
    });
  }

  /* El punto que se está ubicando: se puede arrastrar para afinar. */
  function dibujarUbicando(capaPuntos) {
    if (modo !== 'ubicar' || !ubicando) return;
    var t = porId[ubicando.id];
    if (t.lat !== null && ubicando.lat !== null && (t.lat !== ubicando.lat || t.lng !== ubicando.lng)) {
      el('circle', { cx: X(t.lng), cy: Y(t.lat), r: 9, class: 'mp-fantasma' }, capaPuntos);
    }
    if (ubicando.lat === null) return;
    var x = X(ubicando.lng), y = Y(ubicando.lat);
    var g = el('g', { class: 'mp-nuevo', transform: 'translate(' + x.toFixed(1) + ' ' + y.toFixed(1) + ')' }, capaPuntos);
    el('circle', { r: 22, class: 'mp-nuevo-onda' }, g);
    el('circle', { r: 11, class: 'mp-nuevo-punto' }, g);
    el('circle', { r: 3, class: 'mp-nuevo-centro' }, g);
    el('text', { x: 18, y: 5, class: 'mp-rot mp-rot-t mp-nuevo-rotulo' }, g).textContent = corto(t.nombre);
  }

  /* El fondo. Devuelve los recuadros de sus rótulos, para que los nombres
     de los territorios no se monten encima. */
  function fondo() {
    var g = el('g', { class: 'mp-fondo' }, mundo);
    var ocupados = [];
    var margen = 600;

    // Una cuadrícula de un kilómetro, apenas visible, como en un plano.
    var km = kmEnPx();
    var paso = km >= 30 ? 1 : (km >= 8 ? 5 : 10);
    var grado = paso / 111.32;
    if (paso * km >= 24) {
      var cuadricula = '';
      var medioX = (ANCHO / 2 + margen) / vista.escala, medioY = (ALTO / 2 + margen) / vista.escala;
      for (var u = Math.floor((vista.cx - medioX) / grado) * grado; u < vista.cx + medioX; u += grado) {
        cuadricula += 'M' + ((u - vista.cx) * vista.escala + ANCHO / 2).toFixed(1) + ' ' + (-margen) + 'V' + (ALTO + margen);
      }
      for (var v = Math.floor((vista.cy - medioY) / grado) * grado; v < vista.cy + medioY; v += grado) {
        cuadricula += 'M' + (-margen) + ' ' + ((vista.cy - v) * vista.escala + ALTO / 2).toFixed(1) + 'H' + (ANCHO + margen);
      }
      el('path', { d: cuadricula, class: 'mp-cuadricula' }, g);
    }

    if (!enSerena()) return ocupados;

    var costa = aPantalla(SERENA.costa);
    var lejos = -4000;
    el('path', {
      d: curva(costa) + ' L' + lejos + ' ' + costa[costa.length - 1][1].toFixed(1) +
        ' L' + lejos + ' ' + costa[0][1].toFixed(1) + ' Z',
      class: 'mp-mar'
    }, g);
    // Líneas de profundidad: la costa corrida mar adentro.
    [10, 24, 44].forEach(function (d, i) {
      el('path', { d: curva(desplazar(costa, d)), class: 'mp-veril mp-veril-' + i }, g);
    });
    el('path', { d: curva(costa), class: 'mp-costa' }, g);

    var ruta5 = aPantalla(SERENA.ruta5);
    var ruta = curva(ruta5);
    el('path', { d: ruta, class: 'mp-ruta-borde' }, g);
    el('path', { d: ruta, class: 'mp-ruta' }, g);
    var avenida = curva(aPantalla(SERENA.avenida));
    el('path', { d: avenida, class: 'mp-avenida-borde' }, g);
    el('path', { d: avenida, class: 'mp-avenida' }, g);

    var rioPts = aPantalla(SERENA.rio);
    var rio = curva(rioPts);
    el('path', { d: rio, class: 'mp-rio-borde' }, g);
    el('path', { d: rio, class: 'mp-rio', id: 'mp-rio-curso' }, g);

    // «Océano Pacífico», en el mar, a la altura de dos tercios del cuadro.
    var yMar = limitar(ALTO * 0.64, 40, ALTO - 90);
    var orilla = costa.reduce(function (m, p) { return Math.abs(p[1] - yMar) < Math.abs(m[1] - yMar) ? p : m; });
    if (orilla[0] > 170) {
      var xMar = Math.min(orilla[0] - 34, ANCHO * 0.34);
      el('text', { x: xMar.toFixed(1), y: yMar.toFixed(1), class: 'mp-rot mp-rot-mar', 'text-anchor': 'end' }, g)
        .textContent = 'Océano Pacífico';
    }

    // «Río Elqui» sigue la curva del río, en el primer tramo que se ve.
    var recorrido = 0, desde = null;
    for (var i = 0; i < rioPts.length; i++) {
      if (i) recorrido += Math.hypot(rioPts[i][0] - rioPts[i - 1][0], rioPts[i][1] - rioPts[i - 1][1]);
      var p = rioPts[i];
      if (desde === null && p[0] > 30 && p[0] < ANCHO - 160 && p[1] > 30 && p[1] < ALTO - 30) desde = recorrido;
    }
    if (desde !== null) {
      var tRio = el('text', { class: 'mp-rot mp-rot-rio', dy: '-7' }, g);
      var tp = el('textPath', { href: '#mp-rio-curso', startOffset: (desde + 70).toFixed(0) }, tRio);
      tp.setAttributeNS('http://www.w3.org/1999/xlink', 'xlink:href', '#mp-rio-curso');
      tp.textContent = 'Río Elqui';
    }

    // El letrero de la Ruta 5, en el tramo visible más cercano al tercio alto
    // y lejos del río, para que no tape el cruce.
    function lejosDelRio(q) {
      for (var k = 1; k < rioPts.length; k++) {
        var a = rioPts[k - 1], b = rioPts[k];
        var vx = b[0] - a[0], vy = b[1] - a[1], largo = vx * vx + vy * vy || 1;
        var t = limitar(((q[0] - a[0]) * vx + (q[1] - a[1]) * vy) / largo, 0, 1);
        if (Math.hypot(q[0] - a[0] - vx * t, q[1] - a[1] - vy * t) < 34) return false;
      }
      return true;
    }
    var visibles = ruta5.filter(function (q) {
      return q[0] > 40 && q[0] < ANCHO - 70 && q[1] > 50 && q[1] < ALTO - 110 && lejosDelRio(q);
    });
    if (visibles.length) {
      var e = visibles.reduce(function (m, q) { return Math.abs(q[1] - ALTO * 0.3) < Math.abs(m[1] - ALTO * 0.3) ? q : m; });
      var rg = el('g', { class: 'mp-escudo', transform: 'translate(' + e[0].toFixed(1) + ' ' + e[1].toFixed(1) + ')' }, g);
      el('rect', { x: -22, y: -10, width: 44, height: 20, rx: 5 }, rg);
      el('text', { x: 0, y: 4, 'text-anchor': 'middle' }, rg).textContent = 'Ruta 5';
      ocupados.push({ x1: e[0] - 24, x2: e[0] + 24, y1: e[1] - 12, y2: e[1] + 12 });
    }

    SERENA.lugares.forEach(function (l) {
      var x = X(l.lng), y = Y(l.lat);
      if (x < 10 || x > ANCHO - 10 || y < 10 || y > ALTO - 10) return;
      if (l.faro) {
        el('circle', { cx: x, cy: y, r: 10, class: 'mp-faro-luz' }, g);
        el('circle', { cx: x, cy: y, r: 4.5, class: 'mp-faro' }, g);
      } else {
        el('rect', { x: x - 4, y: y - 4, width: 8, height: 8, class: 'mp-lugar', transform: 'rotate(45 ' + x + ' ' + y + ')' }, g);
      }
      var dx = l.faro ? 14 : 10;
      el('text', { x: x + dx, y: y + 4, class: 'mp-rot mp-rot-lugar' }, g).textContent = l.nombre;
      ocupados.push({ x1: x - 10, x2: x + dx + l.nombre.length * 6.4, y1: y - 10, y2: y + 10 });
    });
    return ocupados;
  }

  /* El nombre de la delegación, sobre su grupo de territorios, como se
     rotulan los barrios en un plano. */
  function rotulosDeDelegacion(puntos, ocupados) {
    var grupos = {};
    puntos.forEach(function (p) {
      (grupos[p.t.delegacion] = grupos[p.t.delegacion] || []).push(p);
    });
    var capa = el('g', { class: 'mp-delegaciones' }, mundo);
    Object.keys(grupos).forEach(function (nombre) {
      var g = grupos[nombre];
      var x = g.reduce(function (s, p) { return s + p.x; }, 0) / g.length;
      var arriba = Math.min.apply(null, g.map(function (p) { return p.y - p.r; }));
      var y = arriba - 30;
      if (x < 40 || x > ANCHO - 40 || y < 18 || y > ALTO - 10) return;
      var w = nombre.length * 7.6;
      var caja = { x1: x - w / 2, x2: x + w / 2, y1: y - 13, y2: y + 4 };
      // Es una ayuda para orientarse: si choca con otro rótulo, no se pone.
      if (ocupados.some(function (q) { return !(caja.x2 < q.x1 || caja.x1 > q.x2 || caja.y2 < q.y1 || caja.y1 > q.y2); })) return;
      var t = el('text', { x: x.toFixed(1), y: y.toFixed(1), 'text-anchor': 'middle', class: 'mp-rot mp-rot-deleg' }, capa);
      t.textContent = nombre;
      ocupados.push(caja);
    });
  }

  /* El nombre va a la derecha del punto; si choca con otro punto u otro
     nombre, prueba a la izquierda, abajo y arriba, en ese orden. */
  function rotular(b, g, ocupados) {
    var texto = corto(b.t.nombre);
    var w = texto.length * 7.2 + 4, x = b.x, y = b.y, r = b.r;
    var opciones = [
      { x: x + r + 9, y: y + 4.5, a: 'start', c: { x1: x + r + 7, x2: x + r + 9 + w, y1: y - 9, y2: y + 8 } },
      { x: x - r - 9, y: y + 4.5, a: 'end', c: { x1: x - r - 9 - w, x2: x - r - 7, y1: y - 9, y2: y + 8 } },
      { x: x, y: y + r + 19, a: 'middle', c: { x1: x - w / 2, x2: x + w / 2, y1: y + r + 6, y2: y + r + 23 } },
      { x: x, y: y - r - 11, a: 'middle', c: { x1: x - w / 2, x2: x + w / 2, y1: y - r - 25, y2: y - r - 8 } }
    ];
    function cabe(o) {
      if (o.c.x1 < 4 || o.c.x2 > ANCHO - 4 || o.c.y1 < 4 || o.c.y2 > ALTO - 4) return false;
      return !ocupados.some(function (q) {
        return !(o.c.x2 < q.x1 || o.c.x1 > q.x2 || o.c.y2 < q.y1 || o.c.y1 > q.y2);
      });
    }
    var elegida = opciones.filter(cabe)[0];
    // Si no cabe en ninguna parte, el nombre se omite (sigue en el globo y
    // para el lector de pantalla), salvo el del elegido y los de la salida.
    var importa = b.t.id === seleccionado || (modo === 'salida' && ruta.indexOf(b.t.id) >= 0);
    if (!elegida && !importa) return;
    elegida = elegida || opciones.filter(function (o) {
      return o.c.x1 >= 4 && o.c.x2 <= ANCHO - 4;
    })[0] || opciones[0];
    ocupados.push(elegida.c);
    var rot = el('text', { x: elegida.x.toFixed(1), y: elegida.y.toFixed(1), 'text-anchor': elegida.a, class: 'mp-rot mp-rot-t' }, g);
    rot.textContent = texto;
  }

  function escala() {
    var km = kmEnPx();
    var opciones = [0.25, 0.5, 1, 2, 5, 10, 20];
    var largo = opciones.filter(function (k) { return k * km <= 130; }).pop() || 0.25;
    var px = largo * km;
    var g = el('g', { class: 'mp-escala', transform: 'translate(' + (ANCHO - px - 20).toFixed(1) + ' ' + (ALTO - 18) + ')' }, mundo);
    el('rect', { x: -8, y: -24, width: px + 16, height: 30, rx: 6, class: 'mp-escala-fondo' }, g);
    el('path', { d: 'M0 -5 V0 H' + px.toFixed(1) + ' V-5' }, g);
    el('text', { x: px / 2, y: -9, 'text-anchor': 'middle' }, g).textContent =
      (largo < 1 ? (largo * 1000) + ' m' : largo + ' km');
    // El norte, arriba: el mapa nunca se gira.
    var n = el('g', { class: 'mp-norte', transform: 'translate(' + (ANCHO - 34) + ' ' + (ALTO - 66) + ')' }, mundo);
    el('path', { d: 'M0 -13 L6 5 L0 1 L-6 5 Z' }, n);
    el('text', { x: 0, y: 18, 'text-anchor': 'middle' }, n).textContent = 'N';
  }

  function punto(b, capaPuntos) {
    var t = b.t, x = b.x, y = b.y, r = b.r;
    var color = colorDe(t), cifra = cifraDe(t);
    var etiqueta = t.nombre + '. ' + (capa === 'cambio'
      ? (t.anterior === null ? '' : 'Este trimestre ' + plural(t.medida, 'actividad', 'actividades') + ', ' + textoCambio(t) + '.')
      : t.semaforo_texto + ': ' + t.hace.toLowerCase() + '. ' + plural(t.medida, 'actividad', 'actividades') + ' en el trimestre.');
    if (modo === 'salida') etiqueta += ruta.indexOf(t.id) >= 0 ? ' Parada ' + (ruta.indexOf(t.id) + 1) + ' de la salida.' : ' Fuera de la salida.';
    var g = el('g', {
      class: 'mp-t mp-' + color + (cifra ? '' : ' mp-cero'),
      tabindex: '0', role: 'button', 'aria-pressed': 'false',
      'data-territorio': t.id, 'aria-label': etiqueta
    }, capaPuntos);
    el('circle', { cx: x, cy: y, r: r + 6, class: 'mp-anillo' }, g);
    el('circle', { cx: x, cy: y, r: r, class: 'mp-punto' }, g);
    if (cifra) {
      el('text', { x: x, y: y + 4.5, 'text-anchor': 'middle', class: 'mp-num' }, g).textContent = cifra;
    }
    g.addEventListener('keydown', function (ev) {
      if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); tocar(t.id, true); }
    });
    g.addEventListener('pointerenter', function () { mostrarTip(t, x, y, r); });
    g.addEventListener('pointerleave', ocultarTip);
    g.addEventListener('focus', function () { if (t.id !== seleccionado) mostrarTip(t, x, y, r); });
    g.addEventListener('blur', ocultarTip);
    return g;
  }

  /* ------------------------------------------------------------ el globo */

  var tip, aviso, franja, avisoEspera = null;

  function mostrarTip(t, x, y, r) {
    if (arrastre || modo === 'ubicar') return;
    tip.textContent = '';
    tip.appendChild(h('b', '', t.nombre));
    var linea;
    if (capa === 'cambio' && t.anterior !== null) {
      linea = plural(t.medida, 'actividad', 'actividades') + ' ahora · ' + t.anterior + ' antes, a la misma altura';
    } else {
      linea = t.hace + ' · ' + plural(t.medida, 'actividad', 'actividades');
    }
    tip.appendChild(h('span', '', linea));
    if (modo === 'salida') {
      tip.appendChild(h('span', 'mp-tip-accion', ruta.indexOf(t.id) >= 0 ? 'Toca para quitarlo de la salida' : 'Toca para agregarlo a la salida'));
    }
    tip.className = 'mp-tip visible';
    var w = tip.offsetWidth, alto = tip.offsetHeight;
    var izq = limitar(x - w / 2, 6, ANCHO - w - 6);
    var arriba = y - r - alto - 12;
    if (arriba < 6) arriba = y + r + 12;
    tip.style.left = izq + 'px';
    tip.style.top = arriba + 'px';
  }

  function ocultarTip() { if (tip) tip.className = 'mp-tip'; }

  function avisar() {
    aviso.classList.add('visible');
    clearTimeout(avisoEspera);
    avisoEspera = setTimeout(function () { aviso.classList.remove('visible'); }, 1400);
  }

  /* ------------------------------------------------------------ moverse */

  var arrastre = null, toques = {}, pinza = null, movido = false, cuadro = null, arrastrePin = false;

  function pedirDibujo() {
    if (cuadro) return;
    cuadro = requestAnimationFrame(function () { cuadro = null; dibujar(); });
  }

  function acotar(v) {
    v.escala = limitar(v.escala, base.escala * 0.35, base.escala * 14);
    return v;
  }

  function zoom(factor, px, py) {
    px = px === undefined ? ANCHO / 2 : px;
    py = py === undefined ? ALTO / 2 : py;
    // El punto bajo el cursor queda donde está.
    var lng = (px - ANCHO / 2) / vista.escala + vista.cx;
    var lat = vista.cy - (py - ALTO / 2) / vista.escala;
    var nueva = acotar({ cx: 0, cy: 0, escala: vista.escala * factor });
    nueva.cx = lng - (px - ANCHO / 2) / nueva.escala;
    nueva.cy = lat + (py - ALTO / 2) / nueva.escala;
    irA(nueva, 180);
  }

  var animacion = null;
  function irA(destino, ms) {
    cancelAnimationFrame(animacion);
    ocultarTip();
    var desde = { cx: vista.cx, cy: vista.cy, escala: vista.escala };
    var hasta = acotar({ cx: destino.cx, cy: destino.cy, escala: destino.escala });
    if (reducir || !ms && ms !== undefined) { vista = hasta; dibujar(); return; }
    var dur = ms || 320, t0 = null;
    function paso(ts) {
      if (t0 === null) t0 = ts;
      var k = Math.min(1, (ts - t0) / dur);
      var e = 1 - Math.pow(1 - k, 3);
      // La escala se interpola en logaritmo: así el acercamiento se siente parejo.
      vista = {
        cx: desde.cx + (hasta.cx - desde.cx) * e,
        cy: desde.cy + (hasta.cy - desde.cy) * e,
        escala: Math.exp(Math.log(desde.escala) + (Math.log(hasta.escala) - Math.log(desde.escala)) * e)
      };
      dibujar();
      if (k < 1) animacion = requestAnimationFrame(paso);
    }
    animacion = requestAnimationFrame(paso);
  }

  function centrarEn(t) {
    if (!t || t.lat === null) return;
    var x = X(t.lng), y = Y(t.lat);
    var dentro = x > ANCHO * 0.15 && x < ANCHO * 0.85 && y > ALTO * 0.15 && y < ALTO * 0.85;
    if (dentro) return;
    irA({ cx: t.lng * kx, cy: t.lat, escala: Math.max(vista.escala, base.escala) });
  }

  function local(ev) {
    var caja = svg.getBoundingClientRect();
    return [(ev.clientX - caja.left) * ANCHO / caja.width, (ev.clientY - caja.top) * ALTO / caja.height];
  }

  function escuchar() {
    svg.addEventListener('pointerdown', function (ev) {
      // El punto que se está ubicando se arrastra; el resto del mapa se mueve.
      if (modo === 'ubicar' && ev.target.closest('.mp-nuevo')) {
        arrastrePin = true;
        movido = true;
        try { svg.setPointerCapture(ev.pointerId); } catch (e) { /* sin captura */ }
        ev.preventDefault();
        return;
      }
      if (ev.pointerType === 'touch') {
        toques[ev.pointerId] = local(ev);
        if (Object.keys(toques).length === 1) movido = false;
        var ids = Object.keys(toques);
        if (ids.length === 2) {
          var a = toques[ids[0]], b = toques[ids[1]];
          pinza = { d: Math.hypot(a[0] - b[0], a[1] - b[1]), m: [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2],
                    vista: { cx: vista.cx, cy: vista.cy, escala: vista.escala } };
          movido = true;
        }
        return;
      }
      if (ev.button !== 0) return;
      cancelAnimationFrame(animacion);
      arrastre = { x: ev.clientX, y: ev.clientY, vista: { cx: vista.cx, cy: vista.cy, escala: vista.escala } };
      movido = false;
    });

    svg.addEventListener('pointermove', function (ev) {
      if (arrastrePin) {
        var q = local(ev);
        ubicando.lat = Math.round(latDe(q[1]) * 1e6) / 1e6;
        ubicando.lng = Math.round(lngDe(q[0]) * 1e6) / 1e6;
        pedirDibujo();
        return;
      }
      if (ev.pointerType === 'touch') {
        if (!(ev.pointerId in toques)) return;
        toques[ev.pointerId] = local(ev);
        var ids = Object.keys(toques);
        if (ids.length !== 2 || !pinza) return;
        ev.preventDefault();
        var a = toques[ids[0]], b = toques[ids[1]];
        var d = Math.hypot(a[0] - b[0], a[1] - b[1]), m = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
        var v = pinza.vista;
        var nueva = acotar({ cx: 0, cy: 0, escala: v.escala * d / (pinza.d || 1) });
        var lng = (pinza.m[0] - ANCHO / 2) / v.escala + v.cx;
        var lat = v.cy - (pinza.m[1] - ALTO / 2) / v.escala;
        nueva.cx = lng - (m[0] - ANCHO / 2) / nueva.escala;
        nueva.cy = lat + (m[1] - ALTO / 2) / nueva.escala;
        vista = nueva;
        pedirDibujo();
        return;
      }
      if (!arrastre) return;
      var dx = ev.clientX - arrastre.x, dy = ev.clientY - arrastre.y;
      if (!movido && Math.abs(dx) + Math.abs(dy) < 5) return;
      if (!movido) {
        movido = true;
        ocultarTip();
        svg.classList.add('arrastrando');
        try { svg.setPointerCapture(ev.pointerId); } catch (e) { /* sin captura */ }
      }
      var caja = svg.getBoundingClientRect(), f = ANCHO / caja.width;
      // Mientras se arrastra solo se corre el dibujo; al soltar se redibuja.
      mundo.setAttribute('transform', 'translate(' + (dx * f).toFixed(1) + ' ' + (dy * f).toFixed(1) + ')');
    });

    function soltar(ev) {
      if (arrastrePin) {
        arrastrePin = false;
        ubicando.error = '';
        pintarFranja();
        return;
      }
      if (ev.pointerType === 'touch') {
        delete toques[ev.pointerId];
        if (Object.keys(toques).length < 2) pinza = null;
        return;
      }
      if (!arrastre) return;
      if (movido) {
        var caja = svg.getBoundingClientRect(), f = ANCHO / caja.width;
        var v = arrastre.vista;
        vista = { cx: v.cx - (ev.clientX - arrastre.x) * f / v.escala,
                  cy: v.cy + (ev.clientY - arrastre.y) * f / v.escala, escala: v.escala };
        svg.classList.remove('arrastrando');
        dibujar();
      }
      arrastre = null;
    }
    svg.addEventListener('pointerup', soltar);
    svg.addEventListener('pointercancel', function (ev) {
      if (arrastrePin) { arrastrePin = false; return; }
      if (ev.pointerType === 'touch') { delete toques[ev.pointerId]; pinza = null; return; }
      if (arrastre && movido) { svg.classList.remove('arrastrando'); dibujar(); }
      arrastre = null;
    });

    // Un clic que terminó un arrastre no elige nada.
    svg.addEventListener('click', function (ev) {
      // El clic se resuelve aquí. Si siguiera hasta el documento, el punto ya
      // redibujado parecería estar fuera del mapa y se elegiría dos veces.
      ev.stopPropagation();
      if (movido) { movido = false; return; }
      if (modo === 'ubicar') {
        var q = local(ev);
        fijarUbicacion(latDe(q[1]), lngDe(q[0]));
        return;
      }
      var g = ev.target.closest('[data-territorio]');
      if (g) tocar(Number(g.getAttribute('data-territorio')), true);
    });

    svg.addEventListener('dblclick', function (ev) {
      ev.preventDefault();
      var p = local(ev);
      zoom(ev.shiftKey ? 1 / 1.8 : 1.8, p[0], p[1]);
    });

    // La rueda sola mueve la página, como siempre; con Ctrl acerca el mapa.
    svg.addEventListener('wheel', function (ev) {
      if (!(ev.ctrlKey || ev.metaKey)) { avisar(); return; }
      ev.preventDefault();
      var p = local(ev);
      zoom(ev.deltaY < 0 ? 1.25 : 1 / 1.25, p[0], p[1]);
    }, { passive: false });

    lienzo.addEventListener('keydown', function (ev) {
      if (ev.target.closest('.mp-controles')) return;
      var paso = 60 / vista.escala, mov = null;
      if (ev.key === '+' || ev.key === '=') { zoom(1.4); ev.preventDefault(); }
      else if (ev.key === '-' || ev.key === '_') { zoom(1 / 1.4); ev.preventDefault(); }
      else if (ev.key === '0') { irA(base); ev.preventDefault(); }
      else if (ev.key === 'ArrowLeft') mov = [-paso, 0];
      else if (ev.key === 'ArrowRight') mov = [paso, 0];
      else if (ev.key === 'ArrowUp') mov = [0, paso];
      else if (ev.key === 'ArrowDown') mov = [0, -paso];
      else if (ev.key === 'Escape') {
        if (modo === 'ubicar') { cancelarUbicar(); ev.preventDefault(); }
        else if (modo === 'salida') { salirDeSalida(); ev.preventDefault(); }
        else if (seleccionado !== null) { volver(); ev.preventDefault(); }
      }
      if (mov) {
        ev.preventDefault();
        irA({ cx: vista.cx + mov[0], cy: vista.cy + mov[1], escala: vista.escala }, 140);
      }
    });
  }

  /* ------------------------------------------------------------ el panel */

  var inicio = document.getElementById('mapa-panel-inicio');

  function fila(dl, termino, valor) {
    var d = h('div', 'mp-par');
    d.appendChild(h('dt', '', termino));
    d.appendChild(h('dd', '', valor));
    dl.appendChild(d);
  }

  function cifra(padre, numero, rotulo, notas, clase) {
    var c = h('div', 'mp-cifra' + (clase ? ' ' + clase : ''));
    c.appendChild(h('span', 'n', String(numero)));
    c.appendChild(h('span', 'r', rotulo));
    [].concat(notas || []).forEach(function (n) {
      if (n) c.appendChild(h('span', 'nota' + (n.clase ? ' ' + n.clase : ''), n.texto || n));
    });
    padre.appendChild(c);
  }

  function boton(texto, clase, accion, ic) {
    var b = h('button', clase);
    b.type = 'button';
    if (ic) b.appendChild(icono(ic, 16));
    b.appendChild(document.createTextNode(texto));
    b.addEventListener('click', accion);
    return b;
  }

  var CHIP = { verde: 'ok', ambar: 'warn', rojo: 'bad', gris: 'off' };

  /* La barra de arriba del panel queda fija al desplazarse: volver a la
     lista y pasar al territorio anterior o siguiente siempre están a mano. */
  function barra(t, alVolver) {
    var b = h('div', 'mp-barra');
    b.appendChild(boton('Volver a la lista', 'btn btn-secondary btn-sm mp-volver', alVolver || volver, IC.atras));
    if (!t) return b;
    var i = orden.indexOf(t.id);
    var pos = h('span', 'mp-pos', (i + 1) + ' de ' + orden.length);
    pos.title = 'Ordenados de más a menos tiempo sin presencia';
    b.appendChild(pos);
    [['Territorio anterior', IC.atras, -1], ['Territorio siguiente', IC.adelante, 1]].forEach(function (x) {
      var btn = h('button', 'mp-paso');
      btn.type = 'button';
      btn.setAttribute('aria-label', x[0]);
      btn.title = x[0];
      btn.appendChild(icono(x[1], 16));
      var destino = orden[i + x[2]];
      if (destino === undefined) btn.disabled = true;
      else btn.addEventListener('click', function () { elegir(destino, { desdePanel: true }); });
      b.appendChild(btn);
    });
    return b;
  }

  function detalle(t) {
    var caja = h('div', 'mapa-detalle');
    caja.appendChild(barra(t));

    var titulo = h('h3', 'mp-titulo', t.nombre);
    titulo.tabIndex = -1;
    caja.appendChild(titulo);
    var sub = h('div', 'mp-sub');
    sub.appendChild(h('span', 'chip ' + CHIP[t.semaforo], t.semaforo_texto));
    sub.appendChild(h('span', '', t.delegacion + ' · ' + t.codigo + (t.activo ? '' : ' · desactivado')));
    caja.appendChild(sub);

    var dl = h('dl', 'mp-datos');
    fila(dl, 'Última presencia', t.ultima ? t.ultima + ' (' + t.hace.toLowerCase() + ')' : 'Ninguna registrada');
    if (datos.modo === 'personal') fila(dl, 'Se cuenta', 'Solo tus actividades');
    if (t.lat === null) fila(dl, 'En el mapa', 'Sin ubicar');
    caja.appendChild(dl);

    var cifras = h('div', 'mp-cifras');
    var notaCambio = null;
    if (t.anterior !== null) {
      var c = cambioDe(t);
      notaCambio = { texto: c === 0 ? 'igual que antes' : (c > 0 ? '▲ ' + c + ' más que antes' : '▼ ' + (-c) + ' menos que antes'),
                     clase: c > 0 ? 'sube' : (c < 0 ? 'baja' : '') };
    }
    cifra(cifras, t.registradas, t.registradas === 1 ? 'actividad' : 'actividades',
      [plural(t.verificadas, 'verificada', 'verificadas'), notaCambio]);
    cifra(cifras, t.abiertos, t.abiertos === 1 ? 'compromiso abierto' : 'compromisos abiertos',
      { texto: t.vencidos ? plural(t.vencidos, 'vencido', 'vencidos') : 'ninguno vencido' }, t.vencidos ? 'mp-alerta' : '');
    cifra(cifras, t.gestiones, t.gestiones === 1 ? 'gestión social' : 'gestiones sociales', 'en el trimestre');
    caja.appendChild(cifras);
    if (notaCambio && comparacion) {
      caja.appendChild(h('p', 'mp-comparado', 'Antes es ' + comparacion.texto + '.'));
    }

    // Lo que se puede hacer va justo después del estado: es para lo que se
    // abre el panel. El detalle de abajo es para quien quiere más contexto.
    var acc = h('div', 'mp-acciones');
    t.acciones.forEach(function (a) {
      if (a.texto === 'Ubicarlo en el mapa' && datos.ubicar && svg) return;
      var link = h('a', 'btn ' + (a.principal ? 'btn-primary' : 'btn-secondary') + ' btn-sm', a.texto);
      link.href = a.url;
      acc.appendChild(link);
    });
    if (datos.ubicar && svg && t.activo) {
      acc.appendChild(boton(t.lat === null ? 'Ubicarlo en el mapa' : 'Corregir la ubicación',
        'btn btn-secondary btn-sm', function () { empezarUbicar(t.id); }));
    }
    if (acc.childNodes.length) caja.appendChild(acc);

    if (t.por_tipo.length) {
      caja.appendChild(h('h4', '', 'Qué se hizo'));
      var max = Math.max.apply(null, t.por_tipo.map(function (x) { return x[1]; }));
      var lista = h('ul', 'mp-tipos');
      t.por_tipo.forEach(function (x) {
        var li = h('li');
        li.appendChild(h('span', 'et', x[0]));
        var barraTipo = h('span', 'bar');
        var lleno = h('i');
        lleno.style.width = Math.max(6, Math.round(100 * x[1] / max)) + '%';
        barraTipo.appendChild(lleno);
        li.appendChild(barraTipo);
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

  function marcarEnMapa() {
    if (!svg) return;
    Object.keys(nodos).forEach(function (k) {
      var activo = String(k) === String(seleccionado);
      nodos[k].classList.toggle('sel', activo);
      nodos[k].setAttribute('aria-pressed', activo ? 'true' : 'false');
      if (zonas[k]) zonas[k].classList.toggle('sel', activo);
    });
    svg.classList.toggle('mp-con-sel', seleccionado !== null && !!nodos[seleccionado]);
    // El elegido va al frente, para que su anillo no quede debajo de otro.
    if (seleccionado !== null && nodos[seleccionado]) nodos[seleccionado].parentNode.appendChild(nodos[seleccionado]);
  }

  /* Un toque en un punto: en una salida lo agrega o lo quita; si no, abre su detalle. */
  function tocar(id, desdeMapa) {
    if (modo === 'salida') { alternarParada(id); return; }
    if (modo === 'ubicar') return;
    elegir(id, { desdeMapa: desdeMapa });
  }

  function elegir(id, op) {
    var t = porId[id];
    if (!t) return;
    if (modo === 'salida') salirDeSalida(true);
    if (modo === 'ubicar') cancelarUbicar(true);
    op = op || {};
    seleccionado = id;
    marcarEnMapa();
    ocultarTip();

    panel.textContent = '';
    panel.scrollTop = 0;
    panel.appendChild(detalle(t));
    marcarFila(id);
    try { history.replaceState(null, '', location.pathname + location.search + '#t-' + id); } catch (e) { /* sin historial */ }

    if (svg && t.lat !== null) centrarEn(t);
    if (!op.desdeMapa && !op.desdePanel) {
      var destino = nodos[id] ? lienzo : panel;
      destino.scrollIntoView({ behavior: reducir ? 'auto' : 'smooth', block: 'center' });
    }
    if (op.desdeMapa && nodos[id]) nodos[id].focus({ preventScroll: true });
    else if (op.desdePanel) {
      var paso = panel.querySelector('.mp-volver');
      if (paso) paso.focus({ preventScroll: true });
    } else {
      var titulo = panel.querySelector('.mp-titulo');
      if (titulo) titulo.focus({ preventScroll: true });
    }
  }

  function mostrarInicio() {
    panel.textContent = '';
    if (inicio) panel.appendChild(inicio);
  }

  function volver() {
    var anterior = seleccionado;
    seleccionado = null;
    marcarEnMapa();
    marcarFila(null);
    mostrarInicio();
    try { history.replaceState(null, '', location.pathname + location.search); } catch (e) { /* nada */ }
    if (anterior !== null && nodos[anterior]) nodos[anterior].focus({ preventScroll: true });
  }

  panel.addEventListener('keydown', function (ev) {
    if (ev.key !== 'Escape') return;
    if (modo === 'salida') { ev.preventDefault(); salirDeSalida(); }
    else if (seleccionado !== null) { ev.preventDefault(); volver(); }
  });

  /* ------------------------------------------------------------ capas */

  function cambiarCapa(nueva) {
    if (nueva === 'cambio' && !comparacion) return;
    capa = nueva;
    document.querySelectorAll('[data-capa]').forEach(function (b) {
      b.setAttribute('aria-pressed', b.getAttribute('data-capa') === capa ? 'true' : 'false');
    });
    var oculto = document.getElementById('f-ver');
    if (oculto) oculto.value = capa === 'cambio' ? 'cambio' : '';
    try {
      var url = new URL(location.href);
      if (capa === 'cambio') url.searchParams.set('ver', 'cambio'); else url.searchParams.delete('ver');
      history.replaceState(null, '', url.pathname + url.search + url.hash);
    } catch (e) { /* sin historial */ }
    if (leyenda) pintarLeyenda();
    ocultarTip();
    dibujar();
    if (seleccionado !== null && porId[seleccionado]) {
      panel.textContent = '';
      panel.appendChild(detalle(porId[seleccionado]));
    }
  }

  /* ------------------------------------------------------------ la salida a terreno */

  function kmEntre(a, b) {
    var k = 111.32, f = Math.cos((a.lat + b.lat) / 2 * Math.PI / 180);
    return Math.hypot((a.lng - b.lng) * k * f, (a.lat - b.lat) * k);
  }

  function largo(ids) {
    var total = 0;
    for (var i = 1; i < ids.length; i++) total += kmEntre(porId[ids[i - 1]], porId[ids[i]]);
    return total;
  }

  function urgencia(t) { return t.dias === null ? 1e6 : t.dias; }

  /* El orden de la visita: se parte por el que lleva más tiempo sin
     presencia, se sigue siempre al más cercano, y después se deshacen los
     cruces (2-opt). Con doce paradas como máximo es instantáneo. */
  function ordenarRuta(ids) {
    if (ids.length < 3) {
      return ids.slice().sort(function (a, b) { return urgencia(porId[b]) - urgencia(porId[a]); });
    }
    var pendientes = ids.slice();
    pendientes.sort(function (a, b) { return urgencia(porId[b]) - urgencia(porId[a]); });
    var orden2 = [pendientes.shift()];
    while (pendientes.length) {
      var ultimo = porId[orden2[orden2.length - 1]];
      pendientes.sort(function (a, b) { return kmEntre(ultimo, porId[a]) - kmEntre(ultimo, porId[b]); });
      orden2.push(pendientes.shift());
    }
    var mejoro = true, vueltas = 0;
    while (mejoro && vueltas++ < 50) {
      mejoro = false;
      for (var i = 1; i < orden2.length - 1; i++) {
        for (var j = i + 1; j < orden2.length; j++) {
          var prueba = orden2.slice(0, i).concat(orden2.slice(i, j + 1).reverse(), orden2.slice(j + 1));
          if (largo(prueba) + 1e-9 < largo(orden2)) { orden2 = prueba; mejoro = true; }
        }
      }
    }
    return orden2;
  }

  function empezarSalida(ids) {
    if (modo === 'ubicar') cancelarUbicar(true);
    seleccionado = null;
    marcarFila(null);
    modo = 'salida';
    ruta = (ids || []).filter(function (id) { return porId[id] && porId[id].lat !== null; }).slice(0, MAXIMO_PARADAS);
    ordenManual = !!(ids && ids.length);
    document.querySelectorAll('[data-armar-salida]').forEach(function (b) { b.setAttribute('aria-pressed', 'true'); });
    pintarSalida();
    dibujar();
    lienzo.scrollIntoView({ behavior: reducir ? 'auto' : 'smooth', block: 'center' });
  }

  function salirDeSalida(sinPanel) {
    modo = null;
    ruta = [];
    document.querySelectorAll('[data-armar-salida]').forEach(function (b) { b.setAttribute('aria-pressed', 'false'); });
    if (!sinPanel) mostrarInicio();
    dibujar();
  }

  function alternarParada(id) {
    var t = porId[id];
    if (!t || t.lat === null) return;
    var i = ruta.indexOf(id);
    if (i >= 0) ruta.splice(i, 1);
    else if (ruta.length >= MAXIMO_PARADAS) { pintarSalida('Una salida tiene como máximo ' + MAXIMO_PARADAS + ' paradas.'); return; }
    else ruta.push(id);
    if (!ordenManual) ruta = ordenarRuta(ruta);
    pintarSalida();
    dibujar();
    if (nodos[id]) nodos[id].focus({ preventScroll: true });
  }

  function moverParada(i, paso) {
    var j = i + paso;
    if (j < 0 || j >= ruta.length) return;
    var x = ruta[i]; ruta[i] = ruta[j]; ruta[j] = x;
    ordenManual = true;
    pintarSalida();
    dibujar();
    var foco = panel.querySelector('[data-mover="' + j + ':' + paso + '"]') || panel.querySelector('.mp-ruta-lista');
    if (foco) foco.focus({ preventScroll: true });
  }

  function pintarSalida(aviso2) {
    panel.textContent = '';
    panel.scrollTop = 0;
    var caja = h('div', 'mapa-salida');
    caja.appendChild(barra(null, function () { salirDeSalida(); }));
    var titulo = h('h3', 'mp-titulo', 'Salida a terreno');
    titulo.tabIndex = -1;
    caja.appendChild(titulo);
    caja.appendChild(h('p', 'mp-ayuda', 'Toca en el mapa los territorios que quieres visitar. El orden se arma solo: ' +
      'parte por el que lleva más tiempo sin presencia y sigue por el más cercano.'));

    var rojos = ubicados.filter(function (t) { return t.semaforo === 'rojo' && t.activo && ruta.indexOf(t.id) < 0; });
    if (rojos.length) {
      caja.appendChild(boton('Agregar ' + (rojos.length === 1 ? 'el que lleva' : 'los ' + rojos.length + ' que llevan') +
        ' más de ' + datos.umbral.ambar + ' días', 'btn btn-secondary btn-sm mp-agregar-rojos', function () {
        rojos.forEach(function (t) { if (ruta.length < MAXIMO_PARADAS) ruta.push(t.id); });
        if (!ordenManual) ruta = ordenarRuta(ruta);
        pintarSalida();
        dibujar();
      }, IC.mas));
    }
    if (aviso2) caja.appendChild(h('p', 'mp-aviso-panel', aviso2));

    if (!ruta.length) {
      caja.appendChild(h('p', 'mp-vacio', 'Todavía no hay paradas.'));
    } else {
      var lista = h('ol', 'mp-ruta-lista');
      lista.tabIndex = -1;
      ruta.forEach(function (id, i) {
        var t = porId[id];
        var li = h('li');
        li.appendChild(h('span', 'mp-ruta-num', String(i + 1)));
        var tx = h('div', 'mp-ruta-tx');
        var nombre = h('b', '', corto(t.nombre));
        nombre.title = t.nombre;
        tx.appendChild(nombre);
        var tramo = i ? ' · ' + kmEntre(porId[ruta[i - 1]], t).toFixed(1).replace('.', ',') + ' km desde la anterior' : '';
        tx.appendChild(h('span', 'mp-ruta-' + t.semaforo, t.hace + tramo));
        li.appendChild(tx);
        [['Subir', 'M12 18.5V5.5M6.5 11 12 5.5l5.5 5.5', -1], ['Bajar', 'M12 5.5v13M6.5 13 12 18.5l5.5-5.5', 1],
         ['Quitar', 'M6.5 6.5l11 11M17.5 6.5l-11 11', 0]].forEach(function (x) {
          var b = h('button', 'mp-paso mp-paso-chico');
          b.type = 'button';
          b.setAttribute('aria-label', x[0] + ' ' + t.nombre);
          b.title = x[0];
          b.appendChild(icono(x[1], 15));
          if (x[2] === 0) b.addEventListener('click', function () { alternarParada(id); });
          else {
            b.setAttribute('data-mover', i + ':' + x[2]);
            if ((x[2] < 0 && i === 0) || (x[2] > 0 && i === ruta.length - 1)) b.disabled = true;
            else b.addEventListener('click', function () { moverParada(i, x[2]); });
          }
          li.appendChild(b);
        });
        lista.appendChild(li);
      });
      caja.appendChild(lista);
      var km = largo(ruta);
      caja.appendChild(h('p', 'mp-ruta-total', plural(ruta.length, 'parada', 'paradas') +
        (ruta.length > 1 ? ' · unos ' + km.toFixed(1).replace('.', ',') + ' km en línea recta' : '')));
    }

    var acc = h('div', 'mp-acciones');
    var ir = h('a', 'btn btn-primary btn-sm', 'Ver la hoja de ruta');
    if (ruta.length) ir.href = datos.salida + '?t=' + ruta.join(',');
    else { ir.setAttribute('aria-disabled', 'true'); ir.classList.add('deshabilitado'); }
    acc.appendChild(ir);
    if (ordenManual && ruta.length > 2) {
      acc.appendChild(boton('Ordenar por cercanía', 'btn btn-secondary btn-sm', function () {
        ordenManual = false;
        ruta = ordenarRuta(ruta);
        pintarSalida();
        dibujar();
      }));
    }
    if (ruta.length) {
      acc.appendChild(boton('Vaciar', 'btn btn-ghost btn-sm', function () {
        ruta = [];
        ordenManual = false;
        pintarSalida();
        dibujar();
      }));
    }
    caja.appendChild(acc);
    panel.appendChild(caja);
  }

  /* ------------------------------------------------------------ ubicar un territorio */

  function latDe(py) { return vista.cy - (py - ALTO / 2) / vista.escala; }
  function lngDe(px) { return ((px - ANCHO / 2) / vista.escala + vista.cx) / kx; }

  function empezarUbicar(id) {
    var t = porId[id];
    if (!t || !datos.ubicar || !svg) return;
    if (modo === 'salida') salirDeSalida(true);
    modo = 'ubicar';
    ubicando = { id: id, lat: t.lat, lng: t.lng, error: '' };
    ocultarTip();
    pintarFranja();
    if (t.lat !== null) centrarEn(t);
    dibujar();
    lienzo.scrollIntoView({ behavior: reducir ? 'auto' : 'smooth', block: 'center' });
    var guardar = franja.querySelector('.btn-primary');
    if (guardar) guardar.focus({ preventScroll: true });
  }

  function fijarUbicacion(lat, lng) {
    if (!ubicando) return;
    ubicando.lat = Math.round(lat * 1e6) / 1e6;
    ubicando.lng = Math.round(lng * 1e6) / 1e6;
    ubicando.error = '';
    pintarFranja();
    dibujar();
  }

  function cancelarUbicar(silencioso) {
    modo = null;
    ubicando = null;
    franja.classList.remove('visible');
    franja.textContent = '';
    if (!silencioso) dibujar();
  }

  function pintarFranja() {
    var t = porId[ubicando.id];
    franja.textContent = '';
    var tx = h('div', 'mp-franja-tx');
    tx.appendChild(h('b', '', 'Ubicando «' + t.nombre + '»'));
    tx.appendChild(h('span', '', ubicando.lat === null
      ? 'Haz clic en el mapa, en el centro del territorio. No pongas la casa de un vecino.'
      : 'Puedes arrastrar el punto para afinar. ' + ubicando.lat.toFixed(5) + ', ' + ubicando.lng.toFixed(5)));
    if (ubicando.error) tx.appendChild(h('span', 'mp-franja-error', ubicando.error));
    franja.appendChild(tx);
    var guardar = boton('Guardar la ubicación', 'btn btn-primary btn-sm', guardarUbicacion);
    var sinCambio = ubicando.lat === null || (ubicando.lat === t.lat && ubicando.lng === t.lng);
    guardar.disabled = sinCambio;
    franja.appendChild(guardar);
    franja.appendChild(boton('Cancelar', 'btn btn-secondary btn-sm', function () { cancelarUbicar(); }));
    franja.classList.add('visible');
  }

  function guardarUbicacion() {
    if (!ubicando || ubicando.lat === null) return;
    var id = ubicando.id;
    var cuerpo = new FormData();
    cuerpo.append('lat', ubicando.lat.toFixed(6));
    cuerpo.append('lng', ubicando.lng.toFixed(6));
    var guardar = franja.querySelector('.btn-primary');
    if (guardar) { guardar.disabled = true; guardar.textContent = 'Guardando…'; }
    fetch(datos.ubicar.url.replace(/\/0\/$/, '/' + id + '/'), {
      method: 'POST', body: cuerpo, credentials: 'same-origin',
      headers: { 'X-CSRFToken': datos.ubicar.csrf, 'X-Requested-With': 'XMLHttpRequest' }
    }).then(function (r) {
      return r.json().catch(function () { return { ok: false, error: 'El servidor no respondió como se esperaba.' }; });
    }).then(function (respuesta) {
      if (respuesta.ok) {
        // Se recarga para que la tabla, la lista «Sin ubicar» y los totales
        // queden al día; el aviso de «Ubicación guardada» lo trae el servidor.
        location.replace(location.pathname + location.search + '#t-' + id);
        location.reload();
        return;
      }
      ubicando.error = respuesta.error || 'No se pudo guardar.';
      pintarFranja();
    }).catch(function () {
      ubicando.error = 'No hay conexión con el servidor. Inténtalo de nuevo.';
      pintarFranja();
    });
  }

  /* ------------------------------------------------------------ arranque */

  // Sin territorios ubicados el mapa igual se dibuja si quien mira puede
  // ubicarlos: es justamente donde se ubican.
  var hayMapa = ubicados.length > 0 || (!!datos.ubicar && datos.territorios.length > 0);
  if (hayMapa) {
    medir();
    encuadrar();
    vista = { cx: base.cx, cy: base.cy, escala: base.escala };
    preparar();
    dibujar();
    if (!ubicados.length) {
      franja.textContent = '';
      franja.appendChild(h('div', 'mp-franja-tx', ''));
      franja.firstChild.appendChild(h('b', '', 'Todavía no hay territorios ubicados'));
      franja.firstChild.appendChild(h('span', '', 'Toca «Ubicarlo» en la lista «Sin ubicar» y haz clic aquí, en el centro del territorio.'));
      franja.classList.add('visible');
    }

    var anchoDibujado = ANCHO, espera = null;
    window.addEventListener('resize', function () {
      clearTimeout(espera);
      espera = setTimeout(function () {
        if (Math.abs((lienzo.clientWidth || 0) - anchoDibujado) < 8) return;
        var factor = vista.escala / base.escala;
        medir();
        encuadrar();
        vista = { cx: vista.cx, cy: vista.cy, escala: base.escala * factor };
        anchoDibujado = ANCHO;
        dibujar();
      }, 150);
    });
  }

  document.addEventListener('click', function (ev) {
    // «Ubicarlo» en la lista de los sin ubicar: se ubica aquí mismo.
    var ubicar = ev.target.closest('[data-ubicar]');
    if (ubicar && hayMapa && datos.ubicar) {
      ev.preventDefault();
      empezarUbicar(Number(ubicar.getAttribute('data-ubicar')));
      return;
    }
    var capaBtn = ev.target.closest('[data-capa]');
    if (capaBtn) { cambiarCapa(capaBtn.getAttribute('data-capa')); return; }
    if (ev.target.closest('[data-armar-salida]')) {
      if (modo === 'salida') salirDeSalida(); else empezarSalida();
      return;
    }
    // Elegir desde la tabla o desde la lista del panel.
    var disparador = ev.target.closest('[data-territorio]');
    if (!disparador || disparador.closest('svg')) return;
    ev.preventDefault();
    var id = Number(disparador.getAttribute('data-territorio'));
    if (modo === 'salida' && !disparador.closest('.mapa-tabla')) { alternarParada(id); return; }
    elegir(id);
  });

  // Pasar sobre una fila de la tabla resalta su punto en el mapa.
  document.querySelectorAll('[data-territorio-fila]').forEach(function (tr) {
    var id = tr.getAttribute('data-territorio-fila');
    tr.addEventListener('mouseenter', function () { if (nodos[id]) nodos[id].classList.add('resalta'); });
    tr.addEventListener('mouseleave', function () { if (nodos[id]) nodos[id].classList.remove('resalta'); });
  });

  // Los filtros se aplican al cambiarlos; el botón queda para quien no
  // tiene JavaScript.
  var filtros = document.querySelector('form[data-autoenvio]');
  if (filtros) {
    filtros.addEventListener('change', function () { filtros.submit(); });
  }

  document.querySelectorAll('[data-capa]').forEach(function (b) {
    b.setAttribute('aria-pressed', b.getAttribute('data-capa') === capa ? 'true' : 'false');
  });

  // Volver desde la hoja de ruta con la salida armada: ?salida=3,2,5
  var salidaPedida = /[?&]salida=([\d,]+)/.exec(location.search);
  var marca = /^#t-(\d+)$/.exec(location.hash);
  if (salidaPedida && hayMapa) {
    empezarSalida(salidaPedida[1].split(',').map(Number));
  } else if (marca && porId[Number(marca[1])]) {
    elegir(Number(marca[1]), { desdeMapa: false });
  }
})();

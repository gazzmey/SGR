/* SGR · relleno inteligente de los formularios.

   El servidor deja en el HTML lo que hace falta (ver comun/relleno.py):

     data-buscador="ayuda"      el selector se usa escribiendo
     data-grupo, data-detalle   en la opción: su grupo y una línea de detalle
     data-nativo                el select se queda con la lista del navegador
     data-filtra='{…}'          las opciones dependen de otro campo
     data-rellena='{…}'         al elegir, completa otros campos
     data-muestra-si='{…}'      el campo se ve solo con cierto valor de otro
     data-autoelige             si hay una sola opción, se elige sola
     data-sugerencias='[…]'     un texto libre que propone valores conocidos
     data-propuesto             el valor inicial es una propuesta, no una elección

   Tres reglas de convivencia:
     1. Lo que la persona eligió a mano no se pisa nunca.
     2. La opción ya elegida no se esconde, aunque no calce con el filtro:
        si está mal, lo dice el servidor al guardar.
     3. Sin JavaScript el formulario funciona igual que antes; esto solo
        ahorra búsquedas. El servidor valida todo como siempre. */
(function () {
  'use strict';

  var reducir = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var LUPA = '<svg class="busc-lupa" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="6.5"/><path d="m16 16 4 4"/></svg>';
  var MAXIMO = 8;

  /* ------------------------------------------------------------ utilidades */

  function leer(json) {
    try { return JSON.parse(json); } catch (e) { return null; }
  }

  /* Minúsculas, sin tildes y con puntos y guiones como espacios: así
     «Peña» encuentra «pena» y «30.000.101-K» encuentra «30000101k». */
  function normalizar(texto) {
    return String(texto || '').normalize('NFD').replace(/[̀-ͯ]/g, '')
      .toLowerCase().replace(/[.\-_/·,]+/g, ' ').replace(/\s+/g, ' ').trim();
  }

  function coincide(indice, consulta) {
    if (!consulta) return true;
    var compacto = indice.replace(/ /g, '');
    var palabras = consulta.split(' ');
    for (var i = 0; i < palabras.length; i++) {
      if (indice.indexOf(palabras[i]) < 0 && compacto.indexOf(palabras[i]) < 0) return false;
    }
    return true;
  }

  /* Un campo del formulario por su nombre. Un grupo de radios llega como
     RadioNodeList, que también tiene .value. */
  function campo(formulario, nombre) {
    return formulario.elements[nombre] || null;
  }

  function valorDe(el) {
    if (!el) return '';
    return el.value || '';
  }

  function opcionElegida(el) {
    if (!el || el.tagName !== 'SELECT') return null;
    return el.options[el.selectedIndex] || null;
  }

  /* Los datos de lo elegido: el data-* de la opción del selector, o de la
     sugerencia elegida en un campo de texto. */
  function datosDe(el) {
    if (!el) return {};
    if (el.tagName === 'SELECT') {
      var op = opcionElegida(el);
      return op && op.value ? op.dataset : {};
    }
    return el._sugerencia || {};
  }

  function contenedor(el) {
    var nodo = el.tagName ? el : el[0];
    return nodo ? nodo.closest('.field') || nodo.parentNode : null;
  }

  /* --------------------------------------------- quién tocó cada campo */

  function esManual(el) { return el.dataset && el.dataset.manual === '1'; }

  function marcarManual(el) {
    if (!el.dataset) return;
    el.dataset.manual = '1';
    delete el.dataset.auto;
    delete el.dataset.propuesto;
    quitarNota(el);
  }

  /* Se puede escribir en un campo vacío, o en uno que completó el sistema.
     Al cargar la página solo se completan los vacíos: lo que trajo el
     servidor —la delegación activa, lo que viene de la ficha— se respeta. */
  function puedeEscribir(el, alCargar) {
    if (!el || el.disabled || esManual(el)) return false;
    if (!valorDe(el)) return true;
    if (alCargar) return false;
    return el.dataset.auto === '1' || el.dataset.propuesto === '1';
  }

  function nota(el, motivo) {
    var caja = contenedor(el);
    if (!caja || !motivo) return;
    var etiqueta = caja.querySelector('label');
    if (!etiqueta) return;
    var marca = etiqueta.querySelector('.auto-nota');
    if (!marca) {
      marca = document.createElement('span');
      marca.className = 'auto-nota';
      etiqueta.appendChild(marca);
    }
    marca.textContent = 'Completado ' + motivo;
    if (!reducir) {
      caja.classList.remove('auto-destello');
      void caja.offsetWidth;
      caja.classList.add('auto-destello');
    }
  }

  function quitarNota(el) {
    var caja = contenedor(el);
    var marca = caja && caja.querySelector('label .auto-nota');
    if (marca) marca.remove();
  }

  /* Escribe un valor como lo haría la persona y avisa a quien escucha. */
  function poner(el, valor, motivo) {
    if (el.tagName === 'SELECT') {
      var todas = el._todas || [];
      var existe = Array.prototype.some.call(el.options, function (op) { return op.value === String(valor); });
      if (!existe) {
        var guardada = todas.filter(function (op) { return op.value === String(valor); })[0];
        if (!guardada) return false;
        el.appendChild(guardada);
      }
    }
    if (el.value === String(valor)) return false;
    el.value = valor;
    if (el.value !== String(valor)) return false;
    el.dataset.auto = '1';
    delete el.dataset.propuesto;
    if (valor) nota(el, motivo); else quitarNota(el);
    var evento = new Event('change', { bubbles: true });
    evento.sgrAuto = true;
    el.dispatchEvent(evento);
    return true;
  }

  /* --------------------------------------------------------------- filtros */

  function aviso(el, texto) {
    var caja = contenedor(el);
    if (!caja) return;
    var linea = caja.querySelector('.filtro-aviso');
    if (!texto) { if (linea) linea.remove(); return; }
    if (!linea) {
      linea = document.createElement('span');
      linea.className = 'help filtro-aviso';
      var ancla = caja.querySelector('.busc') || caja.querySelector('.selw') || el;
      ancla.insertAdjacentElement('afterend', linea);
    }
    linea.textContent = texto;
  }

  function filtrar(formulario, el, cfg, alCargar) {
    var origen = campo(formulario, cfg.segun);
    if (!origen) return;
    var criterio = cfg.de ? (datosDe(origen)[cfg.de] || '') : valorDe(origen);
    if (!el._todas) el._todas = Array.prototype.slice.call(el.options);
    var elegida = el.value;

    function calza(op) {
      if (!criterio) return true;
      var dato = op.getAttribute('data-' + cfg.dato) || '';
      return cfg.lista ? (' ' + dato + ' ').indexOf(' ' + criterio + ' ') >= 0 : dato === String(criterio);
    }

    /* Si lo elegido lo puso el sistema y ya no calza, se suelta. */
    var opElegida = el._todas.filter(function (op) { return op.value === elegida; })[0];
    if (elegida && opElegida && !calza(opElegida) && !esManual(el) && !alCargar) {
      elegida = '';
      el.value = '';
      delete el.dataset.auto;
      quitarNota(el);
    }

    var quedan = el._todas.filter(function (op) {
      return !op.value || op.value === elegida || calza(op);
    });
    var actuales = Array.prototype.slice.call(el.options);
    var igual = actuales.length === quedan.length && actuales.every(function (op, i) { return op === quedan[i]; });
    if (!igual) {
      el.innerHTML = '';
      quedan.forEach(function (op) { el.appendChild(op); });
      el.value = elegida;
    }

    /* El aviso bajo el campo solo cuando explica algo: por qué se acotó
       la lista (si el filtro lo declara) o por qué quedó vacía. */
    var reales = quedan.filter(function (op) { return op.value; });
    var total = el._todas.filter(function (op) { return op.value; }).length;
    if (criterio && reales.length === 0) {
      aviso(el, cfg.vacio || 'No hay opciones para lo elegido arriba.');
    } else if (criterio && cfg.aviso && reales.length < total) {
      aviso(el, cfg.aviso);
    } else {
      aviso(el, '');
    }

    if (cfg.autoelige && criterio && reales.length === 1 && !el.value && puedeEscribir(el, alCargar)) {
      poner(el, reales[0].value, 'porque es la única posible');
    }
    refrescarBuscador(el);
  }

  /* -------------------------------------------------------------- rellenos */

  function rellenar(formulario, origen, alCargar) {
    var destinos = leer(origen.dataset.rellena);
    if (!destinos) return;
    var datos = datosDe(origen);
    Object.keys(destinos).forEach(function (nombre) {
      var destino = campo(formulario, nombre);
      var valor = datos[destinos[nombre]];
      if (!destino || destino.tagName === undefined || !valor) return;
      if (!puedeEscribir(destino, alCargar)) return;
      poner(destino, valor, origen.dataset.motivo || '');
    });
  }

  /* ------------------------------------------------------- mostrar según */

  function mostrar(formulario, el, cfg) {
    var caja = contenedor(el);
    var origen = campo(formulario, cfg.segun);
    if (!caja || !origen) return;
    caja.hidden = valorDe(origen) !== cfg.valor;
  }

  /* ------------------------------------------------- un formulario completo */

  function preparar(formulario) {
    var filtros = [], muestras = [], profundidad = 0;
    formulario.querySelectorAll('[data-filtra]').forEach(function (el) {
      var cfg = leer(el.dataset.filtra);
      if (cfg) filtros.push({ el: el, cfg: cfg });
    });
    formulario.querySelectorAll('[data-muestra-si]').forEach(function (el) {
      var cfg = leer(el.dataset.muestraSi);
      if (cfg) muestras.push({ el: el, cfg: cfg });
    });

    function alCambiar(nombre, alCargar) {
      if (profundidad > 8) return;
      profundidad++;
      var origen = campo(formulario, nombre);
      if (origen && origen.dataset && origen.dataset.rellena) rellenar(formulario, origen, alCargar);
      filtros.forEach(function (f) { if (f.cfg.segun === nombre) filtrar(formulario, f.el, f.cfg, alCargar); });
      muestras.forEach(function (m) { if (m.cfg.segun === nombre) mostrar(formulario, m.el, m.cfg); });
      profundidad--;
    }

    formulario.addEventListener('change', function (e) {
      var el = e.target;
      if (!el.name) return;
      if (e.isTrusted || e.sgrUsuario) marcarManual(el);
      alCambiar(el.name, false);
    });
    formulario.addEventListener('input', function (e) {
      if (e.isTrusted && e.target.name && e.target.tagName !== 'SELECT') marcarManual(e.target);
    });

    /* Al cargar: filtros, rellenos de lo que ya viene elegido, únicos y
       campos que dependen de otro. Solo se completa lo que está vacío. */
    filtros.forEach(function (f) { filtrar(formulario, f.el, f.cfg, true); });
    formulario.querySelectorAll('[data-rellena]').forEach(function (el) {
      if (valorDe(el)) rellenar(formulario, el, true);
    });
    formulario.querySelectorAll('select[data-autoelige]').forEach(function (el) {
      var reales = Array.prototype.filter.call(el.options, function (op) { return op.value; });
      if (!el.value && reales.length === 1) poner(el, reales[0].value, 'porque es la única posible');
    });
    muestras.forEach(function (m) { mostrar(formulario, m.el, m.cfg); });

    formulario.querySelectorAll('select[data-buscador]').forEach(buscador);
    formulario.querySelectorAll('input[data-sugerencias]').forEach(sugerencias);
  }

  /* ---------------------------------------------- lista de coincidencias */

  /* La parte visible que comparten el buscador, el selector y las
     sugerencias: una lista bajo el campo que se recorre con el teclado.

     opciones.alEnfocar   se llama al entrar al campo
     opciones.abreAlEnfocar  false: se abre con clic, flechas, Enter o
                          escribiendo, como un desplegable común
     opciones.marcaElegida  al abrir, se marca la opción ya elegida */
  function lista(input, opciones) {
    var id = (input.id || input.name) + '-lista';
    var panel = document.createElement('div');
    panel.className = 'busc-lista';
    panel.id = id;
    panel.setAttribute('role', 'listbox');
    panel.hidden = true;
    input.setAttribute('role', 'combobox');
    input.setAttribute('aria-autocomplete', 'list');
    input.setAttribute('aria-expanded', 'false');
    input.setAttribute('aria-controls', id);
    input.setAttribute('autocomplete', 'off');

    var filas = [], activa = -1, tecleado = '', tecleadoEspera = null;

    function cerrar() {
      panel.hidden = true;
      input.setAttribute('aria-expanded', 'false');
      input.removeAttribute('aria-activedescendant');
      activa = -1;
    }

    function marcar(i) {
      filas.forEach(function (f, j) { f.el.classList.toggle('activa', j === i); });
      activa = i;
      if (filas[i]) {
        input.setAttribute('aria-activedescendant', filas[i].el.id);
        filas[i].el.scrollIntoView({ block: 'nearest' });
      }
    }

    /* Si abajo no cabe y arriba hay más espacio, la lista se abre hacia
       arriba: así no queda cortada al final de la pantalla. */
    function ubicar() {
      panel.classList.remove('arriba');
      var caja = input.getBoundingClientRect();
      var alto = Math.min(panel.scrollHeight, 320);
      var abajo = window.innerHeight - caja.bottom;
      if (abajo < alto + 12 && caja.top > abajo) panel.classList.add('arriba');
    }

    function abrir() {
      var grupos = opciones.resultados(input.value);
      panel.innerHTML = '';
      filas = [];
      var n = 0;
      grupos.forEach(function (g) {
        if (!g.items.length && !g.vacio) return;
        if (g.titulo) {
          var t = document.createElement('div');
          t.className = 'busc-grupo';
          t.textContent = g.titulo;
          panel.appendChild(t);
        }
        g.items.forEach(function (item) {
          var fila = document.createElement('div');
          fila.className = 'busc-op' + (item.vacia ? ' vacia' : '');
          fila.id = id + '-' + (n++);
          fila.setAttribute('role', 'option');
          fila.setAttribute('aria-selected', item.elegida ? 'true' : 'false');
          var b = document.createElement('b');
          b.textContent = item.texto;
          fila.appendChild(b);
          if (item.detalle) {
            var s = document.createElement('span');
            s.textContent = item.detalle;
            fila.appendChild(s);
          }
          fila.addEventListener('mousedown', function (e) { e.preventDefault(); });
          fila.addEventListener('click', function () { opciones.elegir(item); cerrar(); });
          panel.appendChild(fila);
          filas.push({ el: fila, item: item });
        });
        if (g.resto) {
          var mas = document.createElement('div');
          mas.className = 'busc-mas';
          mas.textContent = 'y ' + g.resto + ' más: sigue escribiendo para acotar.';
          panel.appendChild(mas);
        }
      });
      if (!filas.length) {
        var nada = document.createElement('div');
        nada.className = 'busc-nada';
        nada.textContent = opciones.sinResultados || 'Sin coincidencias. Revisa lo que escribiste.';
        panel.appendChild(nada);
      }
      panel.hidden = false;
      input.setAttribute('aria-expanded', 'true');
      ubicar();
      /* Se adelanta la primera coincidencia solo cuando se escribió algo:
         así un Enter al entrar al campo no elige nada por accidente. En un
         selector se marca lo ya elegido, como en un desplegable común. */
      var escrito = opciones.consulta ? opciones.consulta(input.value) : input.value;
      var elegida = -1;
      if (!escrito && opciones.marcaElegida) {
        filas.forEach(function (f, i) { if (f.item.elegida) elegida = i; });
      }
      marcar(escrito && filas.length ? 0 : elegida);
    }

    /* En un selector que no se escribe, una letra salta a la primera
       opción que empieza así; varias seguidas, a la que empieza con esas. */
    function saltar(letra) {
      clearTimeout(tecleadoEspera);
      tecleado += normalizar(letra) || letra;
      tecleadoEspera = setTimeout(function () { tecleado = ''; }, 700);
      var desde = tecleado.length > 1 ? Math.max(activa, 0) : activa + 1;
      for (var k = 0; k < filas.length; k++) {
        var i = (desde + k) % filas.length;
        if (normalizar(filas[i].item.texto).indexOf(tecleado) === 0) { marcar(i); return; }
      }
    }

    input.addEventListener('keydown', function (e) {
      if (input.disabled) return;
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        if (panel.hidden) { abrir(); return; }
        if (!filas.length) return;
        var siguiente = activa + (e.key === 'ArrowDown' ? 1 : -1);
        marcar((siguiente + filas.length) % filas.length);
      } else if (e.key === 'Enter') {
        if (!panel.hidden && filas[activa]) {
          e.preventDefault();
          opciones.elegir(filas[activa].item);
          cerrar();
        } else if (panel.hidden && opciones.abreConEnter) {
          e.preventDefault();
          abrir();
        }
      } else if (e.key === 'Escape') {
        if (!panel.hidden) { e.preventDefault(); cerrar(); opciones.restaurar(); }
      } else if (input.readOnly && e.key === ' ') {
        e.preventDefault();
        if (panel.hidden) abrir();
        else if (filas[activa]) { opciones.elegir(filas[activa].item); cerrar(); }
      } else if (input.readOnly && e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
        if (panel.hidden) abrir();
        saltar(e.key);
      } else if (e.key === 'Tab' && !panel.hidden) {
        cerrar();
      }
    });
    input.addEventListener('input', abrir);
    input.addEventListener('focus', function () {
      if (opciones.alEnfocar) opciones.alEnfocar();
      if (opciones.abreAlEnfocar !== false) abrir();
    });
    input.addEventListener('click', function () {
      if (panel.hidden && !input.disabled) abrir();
    });
    input.addEventListener('blur', function () {
      setTimeout(function () { cerrar(); opciones.restaurar(); }, 120);
    });

    return panel;
  }

  /* ------------------------------------- buscador y selector de un select */

  var FLECHA = '<svg class="busc-flecha" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m6 9.5 6 6 6-6"/></svg>';

  /* Cuántas opciones aguanta un selector antes de que convenga escribir. */
  var PARA_ESCRIBIR = 8;

  /* El buscador: un selector largo (vecinos, personas) que se usa
     escribiendo. Muestra unas pocas coincidencias a la vez. */
  function buscador(sel) {
    combo(sel, {
      lupa: true, escribe: true, limite: MAXIMO,
      ayuda: function () { return sel.dataset.buscador; },
      sinResultados: 'Sin coincidencias. Prueba con el apellido, el RUT o el código.'
    });
  }

  /* El selector: cualquier otro desplegable de un formulario. Se ve como
     siempre, pero la lista la dibuja el sistema: con el detalle de cada
     opción, agrupada si las opciones traen grupo, y con la elegida marcada.
     Si es larga, además se puede escribir para acotarla. */
  function selector(sel) {
    if (sel._buscador || sel.multiple || sel.hasAttribute('data-nativo') ||
        sel.hasAttribute('data-autoenviar') || !sel.closest('.field')) return;
    var reales = Array.prototype.filter.call(sel.options, function (op) { return op.value; });
    var largo = (sel._todas || reales).length > PARA_ESCRIBIR;
    combo(sel, {
      lupa: false, escribe: largo, limite: Infinity,
      ayuda: function () {
        var vacia = Array.prototype.filter.call(sel.options, function (op) { return !op.value; })[0];
        return vacia ? vacia.textContent.trim() : 'Elige una opción';
      },
      sinResultados: 'Ninguna opción calza con lo que escribiste.'
    });
  }

  function combo(sel, cfg) {
    if (sel._buscador) return;
    var envoltura = sel.closest('.selw') || sel;
    var caja = document.createElement('div');
    caja.className = cfg.lupa ? 'busc' : 'busc combo';
    if (cfg.lupa) caja.innerHTML = LUPA;
    var input = document.createElement('input');
    input.type = 'text';
    input.className = 'input busc-in';
    input.id = (sel.id || sel.name) + (cfg.lupa ? '-buscar' : '-elegir');
    input.spellcheck = false;
    input.readOnly = !cfg.escribe;
    caja.appendChild(input);
    /* La flecha va después del campo, para que el CSS la gire al abrir. */
    if (!cfg.lupa) caja.insertAdjacentHTML('beforeend', FLECHA);

    /* La etiqueta pasa a apuntar al campo visible, y el select queda
       oculto pero dentro del formulario: es el que viaja al servidor. */
    var etiqueta = sel.id && document.querySelector('label[for="' + sel.id + '"]');
    if (etiqueta) etiqueta.htmlFor = input.id;
    if (sel.required) { sel.required = false; sel.dataset.requerido = '1'; }
    envoltura.hidden = true;
    envoltura.insertAdjacentElement('afterend', caja);
    sel._buscador = input;

    var tituloRecientes = sel.dataset.recientes || 'Usados hace poco';

    function vacia() {
      return Array.prototype.filter.call(sel.options, function (op) { return !op.value; })[0];
    }

    function item(op) {
      return {
        valor: op.value,
        texto: (op.dataset.nombre || op.textContent).trim(),
        detalle: op.dataset.detalle || '',
        grupo: op.dataset.grupo || '',
        vacia: !op.value,
        elegida: op.value === sel.value && !!op.value,
        indice: normalizar(op.textContent + ' ' + (op.dataset.detalle || '') + ' ' +
                           (op.dataset.grupo || '') + ' ' + (op.dataset.busca || ''))
      };
    }

    /* Agrupa respetando el orden en que vienen; sin grupos, una sola lista. */
    function agrupar(items) {
      var grupos = [], porTitulo = {};
      items.forEach(function (it) {
        var titulo = it.grupo;
        if (!porTitulo[titulo]) {
          porTitulo[titulo] = { titulo: titulo, items: [] };
          grupos.push(porTitulo[titulo]);
        }
        porTitulo[titulo].items.push(it);
      });
      return grupos;
    }

    function recortar(items) {
      if (cfg.limite === Infinity) return agrupar(items);
      return [{ items: items.slice(0, cfg.limite), resto: Math.max(0, items.length - cfg.limite) }];
    }

    var panel = lista(input, {
      resultados: function (texto) {
        var consulta = normalizar(texto === textoElegido() ? '' : texto);
        var todas = Array.prototype.filter.call(sel.options, function (op) { return op.value; }).map(item);
        if (consulta) {
          return recortar(todas.filter(function (it) { return coincide(it.indice, consulta); }));
        }
        var grupos = [];
        var recientes = todas.filter(function (it) {
          var op = Array.prototype.filter.call(sel.options, function (o) { return o.value === it.valor; })[0];
          return op && op.dataset.reciente;
        });
        /* La opción vacía sirve para quitar lo elegido en un campo
           opcional; si no hay nada elegido, no hace falta ofrecerla. */
        var v = vacia();
        if (v && !sel.dataset.requerido && sel.value) {
          var quitar = item(v);
          if (/^elige/i.test(quitar.texto)) quitar.texto = 'Quitar la selección';
          grupos.push({ items: [quitar] });
        }
        if (recientes.length) grupos.push({ titulo: tituloRecientes, items: recientes });
        var resto = todas.filter(function (it) {
          return !recientes.some(function (r) { return r.valor === it.valor; });
        });
        var cuerpo = recortar(resto);
        if (recientes.length && cuerpo.length === 1 && !cuerpo[0].titulo) cuerpo[0].titulo = 'Todos';
        return grupos.concat(cuerpo);
      },
      consulta: function (texto) { return texto === textoElegido() ? '' : texto.trim(); },
      elegir: elegir,
      restaurar: function () {
        /* Borrar el texto de un campo opcional y salir lo deja vacío. */
        if (cfg.escribe && !input.value.trim() && sel.value && !sel.dataset.requerido && vacia()) {
          elegir({ valor: '' });
          return;
        }
        refrescar();
      },
      alEnfocar: function () { if (cfg.escribe) input.select(); },
      abreAlEnfocar: cfg.lupa,
      abreConEnter: true,
      marcaElegida: !cfg.lupa,
      sinResultados: cfg.sinResultados
    });
    caja.appendChild(panel);

    function elegir(it) {
      sel.value = it.valor;
      marcarManual(sel);
      quitarFalta(sel);
      var evento = new Event('change', { bubbles: true });
      evento.sgrUsuario = true;
      sel.dispatchEvent(evento);
      refrescar();
    }

    function textoElegido() {
      var op = opcionElegida(sel);
      return op && op.value ? (op.dataset.nombre || op.textContent).trim() : '';
    }

    function refrescar() {
      input.placeholder = cfg.ayuda() || '';
      input.value = textoElegido();
      input.title = input.value;
      input.disabled = sel.disabled;
      caja.classList.toggle('con-valor', !!sel.value);
      caja.classList.toggle('desactivado', sel.disabled);
    }

    sel.addEventListener('change', function () { quitarFalta(sel); refrescar(); });
    sel._refrescar = refrescar;
    /* Otras partes del sistema rehacen las opciones o desactivan el select
       (la subatención según el tipo, los filtros de arriba): el campo
       visible se pone al día solo. */
    if (window.MutationObserver) {
      new MutationObserver(refrescar).observe(sel, {
        childList: true, attributes: true, attributeFilter: ['disabled']
      });
    }
    refrescar();
  }

  function refrescarBuscador(sel) {
    if (sel._refrescar) sel._refrescar();
  }

  /* Un select obligatorio que se volvió buscador o selector deja de tener
     «required» (está oculto), así que se revisa al enviar: sin esto, el
     aviso llegaría recién desde el servidor. */
  function marcarFalta(sel) {
    var caja = contenedor(sel);
    if (!caja) return;
    caja.classList.add('err');
    if (!caja.querySelector('.msg.falta-eleccion')) {
      var msg = document.createElement('span');
      msg.className = 'msg falta-eleccion';
      msg.innerHTML = '<svg class="i" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7.5v5M12 16.2h.01"/></svg>Elige una opción de la lista.';
      caja.appendChild(msg);
    }
  }

  function quitarFalta(sel) {
    var caja = contenedor(sel);
    var msg = caja && caja.querySelector('.msg.falta-eleccion');
    if (!msg) return;
    msg.remove();
    if (!caja.querySelector('.msg')) caja.classList.remove('err');
  }

  function exigirElegidos(formulario) {
    if (formulario._exige) return;
    formulario._exige = true;
    formulario.addEventListener('submit', function (e) {
      var primero = null;
      formulario.querySelectorAll('select[data-requerido]').forEach(function (sel) {
        var caja = contenedor(sel);
        if (sel.value || sel.disabled || !sel._buscador || (caja && caja.hidden)) return;
        marcarFalta(sel);
        if (!primero) primero = sel;
      });
      if (primero) {
        e.preventDefault();
        e.stopPropagation();
        primero._buscador.focus();
      }
    }, true);
  }

  /* ------------------------------------- sugerencias de un campo de texto */

  function sugerencias(input) {
    var valores = leer(input.dataset.sugerencias);
    if (!valores || !valores.length) return;
    var caja = document.createElement('div');
    caja.className = 'busc busc-texto';
    input.insertAdjacentElement('beforebegin', caja);
    caja.appendChild(input);
    valores.forEach(function (v) { v.indice = normalizar(v.valor + ' ' + (v.detalle || '') + ' ' + (v.busca || '')); });

    var panel = lista(input, {
      resultados: function (texto) {
        var consulta = normalizar(texto);
        var hallados = valores.filter(function (v) { return coincide(v.indice, consulta); });
        return [{
          titulo: consulta ? '' : 'Registrados en la delegación',
          items: hallados.slice(0, MAXIMO).map(fila),
          resto: Math.max(0, hallados.length - MAXIMO)
        }];
      },
      consulta: function (texto) { return texto.trim(); },
      elegir: function (it) {
        input.value = it.valor;
        input._sugerencia = it.datos;
        marcarManual(input);
        var evento = new Event('change', { bubbles: true });
        evento.sgrUsuario = true;
        input.dispatchEvent(evento);
      },
      restaurar: function () {},
      sinResultados: 'No está registrado: se guarda tal como lo escribiste.'
    });
    caja.appendChild(panel);

    function fila(v) {
      return { valor: v.valor, texto: v.valor, detalle: v.detalle || '', datos: v };
    }

    /* Escribir a mano suelta la sugerencia elegida, salvo que el texto
       siga siendo exactamente el mismo. */
    input.addEventListener('input', function () {
      if (input._sugerencia && input.value !== input._sugerencia.valor) input._sugerencia = null;
    });
  }

  /* ------------------------------------------------------------- arranque */

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('form').forEach(function (formulario) {
      if (formulario.querySelector('[data-buscador], [data-filtra], [data-rellena], [data-muestra-si], [data-autoelige], [data-sugerencias]')) {
        preparar(formulario);
      }
      /* Los desplegables de los formularios que guardan algo usan la lista
         del sistema. Los filtros de los listados se quedan como están. */
      if ((formulario.getAttribute('method') || '').toLowerCase() === 'post') {
        formulario.querySelectorAll('.field select.input').forEach(selector);
      }
      if (formulario.querySelector('select[data-requerido]')) exigirElegidos(formulario);
    });
  });
})();

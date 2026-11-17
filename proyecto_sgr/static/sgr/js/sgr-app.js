/* SGR · comportamiento del lado del navegador en la versión Django.
   =========================================================================
   Es deliberadamente corto. En la maqueta estática el navegador hacía todo:
   filtrar, ordenar, paginar, exportar. Aquí eso lo hace el servidor, y lo
   que queda en JavaScript es solo lo que mejora el uso sin ser necesario:

     · enviar el formulario al cambiar un desplegable
     · confirmar antes de una acción que cambia datos
     · convertir los mensajes de Django en avisos flotantes
     · la subatención que depende del tipo, en el ingreso de atención
     · el medidor de fuerza de la contraseña nueva
     · las seis casillas del código de recuperación
     · la meta y el ponderador sugeridos al crear una meta

   Todo lo de arriba funciona igual sin JavaScript: los formularios tienen
   su botón de enviar, y la validación que manda es la del servidor.
   ========================================================================= */

(function () {
  'use strict';

  /* ---------------------------------------------------------------------
     0. Confirmaciones y resultados: SweetAlert2, con respaldo propio

     Las confirmaciones y los resultados se muestran con SweetAlert2, como
     pide la entrega. SweetAlert2 llega desde un servidor externo
     (cdn.jsdelivr.net), y si esa descarga falla —una red que la bloquea,
     una conexión lenta— antes el resultado de guardar simplemente no se
     veía. Ahora, sin SweetAlert2, se abre un diálogo propio con el mismo
     aspecto, hecho con el elemento <dialog> del navegador (foco atrapado,
     Escape para cerrar, fondo que bloquea la página).

     dialogo({...}) devuelve una promesa con {confirmado, negado}, o null si
     no hay ni SweetAlert2 ni <dialog>: quien llama usa entonces su respaldo
     (el confirm() del navegador o el aviso escrito en la página).
     --------------------------------------------------------------------- */

  function conSweetAlert(op) {
    var opciones = {
      icon: op.icono || 'info',
      title: op.titulo || '',
      confirmButtonText: op.aceptar || 'Entendido',
      buttonsStyling: false,
      customClass: { popup: 'sgr-swal' + (op.peligro ? ' peligro' : ''), container: 'sgr-fondo' }
    };
    if (op.html) opciones.html = op.html; else opciones.text = op.texto || '';
    if (op.cancelar) {
      opciones.showCancelButton = true;
      opciones.cancelButtonText = op.cancelar;
      opciones.reverseButtons = true;
      opciones.focusCancel = !!op.enfocarCancelar;
    }
    if (op.negar) {
      opciones.showDenyButton = true;
      opciones.denyButtonText = op.negar;
      opciones.reverseButtons = true;
    }
    return window.Swal.fire(opciones).then(function (r) {
      return { confirmado: !!r.isConfirmed, negado: !!r.isDenied };
    });
  }

  var TRAZO = 'width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
              'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"';
  var ICONOS = {
    warning: '<svg ' + TRAZO + '><path d="M12 6.5v7M12 17.5h.01"/></svg>',
    error: '<svg ' + TRAZO + '><path d="M7.5 7.5l9 9M16.5 7.5l-9 9"/></svg>',
    success: '<svg ' + TRAZO + '><path d="m5.5 12.5 4.2 4.2L18.5 8"/></svg>',
    info: '<svg ' + TRAZO + '><path d="M12 11v6M12 7h.01"/></svg>',
    question: '<svg ' + TRAZO + '><path d="M9.2 9.2a2.9 2.9 0 1 1 3.9 2.7c-.7.3-1.1.9-1.1 1.6v.5M12 17.5h.01"/></svg>'
  };
  var contadorDialogos = 0;

  function dialogo(op) {
    if (typeof window.Swal !== 'undefined') return conSweetAlert(op);
    if (typeof window.HTMLDialogElement !== 'function') return null;
    return new Promise(function (resolver) {
      var id = 'sgr-dialogo-' + (++contadorDialogos);
      var d = document.createElement('dialog');
      d.className = 'sgr-dialogo' + (op.peligro ? ' peligro' : '');
      d.setAttribute('aria-labelledby', id + '-t');
      var caja = document.createElement('div');
      caja.className = 'dlg-caja';
      if (ICONOS[op.icono]) {
        var icono = document.createElement('div');
        icono.className = 'dlg-ic ' + op.icono;
        icono.innerHTML = ICONOS[op.icono];
        caja.appendChild(icono);
      }
      var titulo = document.createElement('h2');
      titulo.id = id + '-t';
      titulo.textContent = op.titulo || '';
      caja.appendChild(titulo);
      if (op.html || op.texto) {
        var texto = document.createElement('div');
        texto.className = 'dlg-tx';
        /* html solo llega desde las plantillas (data-confirmar-texto); lo
           que viene de lo que escribe la gente va siempre como texto. */
        if (op.html) texto.innerHTML = op.html; else texto.textContent = op.texto;
        caja.appendChild(texto);
      }
      var acciones = document.createElement('div');
      acciones.className = 'dlg-acc';
      caja.appendChild(acciones);
      d.appendChild(caja);

      var resuelto = false;
      function cerrar(valor) {
        if (resuelto) return;
        resuelto = true;
        d.close();
        d.remove();
        resolver({ confirmado: valor === 'aceptar', negado: valor === 'negar' });
      }
      function boton(rotulo, clase, valor) {
        var b = document.createElement('button');
        b.type = 'button';
        b.className = 'btn ' + clase;
        b.textContent = rotulo;
        b.addEventListener('click', function () { cerrar(valor); });
        acciones.appendChild(b);
        return b;
      }
      var cancelar = op.cancelar ? boton(op.cancelar, 'btn-secondary', 'cancelar') : null;
      if (op.negar) boton(op.negar, 'btn-secondary', 'negar');
      var aceptar = boton(op.aceptar || 'Entendido', op.peligro ? 'btn-peligro' : 'btn-primary', 'aceptar');

      /* Escape y un clic fuera de la caja cierran como «cancelar». */
      d.addEventListener('cancel', function (e) { e.preventDefault(); cerrar('cancelar'); });
      d.addEventListener('click', function (e) { if (e.target === d) cerrar('cancelar'); });

      document.body.appendChild(d);
      d.showModal();
      (op.enfocarCancelar && cancelar ? cancelar : aceptar).focus();
    });
  }
  window.sgrDialogo = dialogo;

  /* ---------------------------------------------------------------------
     1. Desplegables que envían su formulario
     --------------------------------------------------------------------- */

  document.addEventListener('change', function (e) {
    var campo = e.target.closest('[data-autoenviar]');
    if (!campo) return;
    var formulario = campo.form;
    if (formulario) formulario.submit();
  });

  /* ---------------------------------------------------------------------
     2. Confirmar antes de cambiar datos

     El botón lleva data-confirmar con el título. Se pregunta con SweetAlert2
     o, si no cargó, con el diálogo propio; en último caso, con el confirm()
     del navegador: la acción nunca queda sin confirmar.
     --------------------------------------------------------------------- */

  document.addEventListener('click', function (e) {
    var boton = e.target.closest('[data-confirmar]');
    if (!boton || boton.dataset.confirmado === 'si') return;

    e.preventDefault();
    var titulo = boton.dataset.confirmar;
    var texto = boton.dataset.confirmarTexto || '';
    var formulario = boton.form || boton.closest('form');

    function seguir() {
      boton.dataset.confirmado = 'si';
      if (formulario) formulario.submit();
      else boton.click();
    }

    var respuesta = dialogo({
      icono: 'warning',
      titulo: titulo,
      html: texto,
      cancelar: 'Cancelar',
      aceptar: 'Sí, continuar',
      peligro: true,
      enfocarCancelar: true
    });
    if (!respuesta) {
      if (window.confirm(titulo + '\n\n' + texto.replace(/<[^>]+>/g, ''))) seguir();
      return;
    }
    respuesta.then(function (r) { if (r.confirmado) seguir(); });
  });

  /* ---------------------------------------------------------------------
     3a. El resultado de la operación, con SweetAlert2 (o su respaldo)

     Lo deja la vista en la sesión DESPUÉS de guardar, así que si este
     diálogo aparece es porque la operación terminó. Nunca se dispara desde
     el formulario: ahí todavía no se sabe si va a funcionar.

     Puede traer hasta dos acciones; es lo que permite ofrecer «registrar
     otra» o «ver la registrada» al terminar una atención.
     --------------------------------------------------------------------- */

  document.addEventListener('DOMContentLoaded', function () {
    var bloque = document.getElementById('sgr-resultado');
    if (!bloque) return;

    var dato;
    try { dato = JSON.parse(bloque.textContent); } catch (e) { return; }
    if (!dato || !dato.titulo) return;

    var acciones = dato.acciones || [];

    var respuesta = dialogo({
      icono: dato.icono || 'success',
      titulo: dato.titulo,
      texto: dato.texto || '',
      aceptar: acciones[0] ? acciones[0].texto : 'Entendido',
      negar: acciones[1] ? acciones[1].texto : ''
    });

    if (!respuesta) {
      /* Sin ningún diálogo, el aviso se escribe en la página: es el mismo
         que trae el <noscript> para quien navega sin JavaScript. */
      var respaldo = bloque.nextElementSibling;
      if (respaldo && respaldo.tagName === 'NOSCRIPT') {
        var aviso = document.createElement('div');
        aviso.innerHTML = respaldo.textContent;
        respaldo.insertAdjacentElement('afterend', aviso);
      }
      return;
    }

    respuesta.then(function (r) {
      if (r.confirmado && acciones[0] && acciones[0].url) {
        window.location.href = acciones[0].url;
      } else if (r.negado && acciones[1] && acciones[1].url) {
        window.location.href = acciones[1].url;
      }
    });
  });

  /* ---------------------------------------------------------------------
     3b. Los mensajes de Django, como avisos flotantes

     Son los avisos menores —un cambio de delegación, un saludo al entrar—,
     no el resultado de una operación. Se quedan además en la página: si
     alguien no ve el aviso al vuelo, el texto sigue ahí arriba.
     --------------------------------------------------------------------- */

  document.addEventListener('DOMContentLoaded', function () {
    var caja = document.querySelector('[data-mensajes]');
    if (!caja || !window.sgrToast) return;
    caja.querySelectorAll('.notice').forEach(function (aviso, i) {
      var texto = (aviso.querySelector('div') || aviso).textContent.trim();
      var tipo = aviso.classList.contains('bad') ? 'bad'
        : aviso.classList.contains('warn') ? 'warn' : '';
      if (texto) setTimeout(function () { window.sgrToast(texto, null, tipo); }, 120 * i);
    });
  });

  /* ---------------------------------------------------------------------
     3c. Un clic, un envío

     Esto es comodidad, no protección: evita el segundo clic impaciente y
     deja claro que algo está pasando. Quien impide de verdad el registro
     duplicado es el servidor, con la ficha de un solo uso de comun/envio.py,
     que también cubre el caso de reenviar el POST o tener JavaScript
     apagado.
     --------------------------------------------------------------------- */

  document.addEventListener('submit', function (e) {
    var formulario = e.target;
    if (!formulario.querySelector('input[name="envio"]')) return;

    var boton = formulario.querySelector('button[type="submit"]');
    if (!boton || boton.dataset.enviando === 'si') return;

    boton.dataset.enviando = 'si';
    boton.dataset.rotulo = boton.textContent;
    boton.textContent = 'Guardando…';
    /* Se deshabilita después del envío en curso, para no cancelarlo. */
    setTimeout(function () { boton.disabled = true; }, 0);
  });

  /* ---------------------------------------------------------------------
     4. Subatención dependiente del tipo

     El select de tipo trae los datos de sus subatenciones en el HTML, así
     que no hace falta ir al servidor por cada cambio. El servidor valida
     igual que la subatención corresponda al tipo elegido.
     --------------------------------------------------------------------- */

  document.addEventListener('DOMContentLoaded', function () {
    var selTipo = document.querySelector('[data-tipo-atencion]');
    var selSub = document.querySelector('[data-subatencion]');
    if (!selTipo || !selSub) return;

    var datos = {};
    try {
      datos = JSON.parse(document.getElementById('subatenciones-por-tipo').textContent);
    } catch (e) { return; }

    var ayuda = document.querySelector('[data-sub-ayuda]');
    var aviso = document.querySelector('[data-doc-aviso]');
    var elegidaAlCargar = selSub.value;

    function cargar(conservar) {
      var tipo = selTipo.value;
      var hijas = datos[tipo] || [];

      selSub.innerHTML = '<option value="">' +
        (tipo ? 'Elige una subatención' : 'Elige primero un tipo') + '</option>';
      hijas.forEach(function (s) {
        var op = document.createElement('option');
        op.value = s.id;
        op.textContent = s.nombre + (s.documento ? ' · exige documento' : '');
        op.dataset.documento = s.documento ? '1' : '';
        if (conservar && String(s.id) === String(elegidaAlCargar)) op.selected = true;
        selSub.appendChild(op);
      });
      selSub.disabled = !tipo;

      if (ayuda) {
        ayuda.textContent = tipo
          ? hijas.length + (hijas.length === 1 ? ' subatención disponible.' : ' subatenciones disponibles.')
          : 'Se habilita al elegir el tipo.';
      }
      revisarDocumento();
    }

    function revisarDocumento() {
      if (!aviso) return;
      var op = selSub.options[selSub.selectedIndex];
      var exige = !!(op && op.dataset.documento);
      aviso.hidden = !exige;
    }

    selTipo.addEventListener('change', function () { cargar(false); });
    selSub.addEventListener('change', revisarDocumento);
    cargar(true);
  });

  /* ---------------------------------------------------------------------
     5. Fuerza de la contraseña nueva

     Solo informa. Quien decide si la contraseña sirve son los validadores
     de Django, en el servidor.
     --------------------------------------------------------------------- */

  document.addEventListener('DOMContentLoaded', function () {
    var campo = document.querySelector('[data-clave]');
    if (!campo) return;

    var medidor = document.querySelector('.meter');
    var rotulo = document.querySelector('.fuerza');
    var reglas = document.querySelectorAll('.reglas li[data-regla]');

    var PRUEBAS = {
      largo: function (v) { return v.length >= 8; },
      letra: function (v) { return /[a-záéíóúñ]/i.test(v); },
      numero: function (v) { return /\d/.test(v); },
      variada: function (v) { return /[A-ZÁÉÍÓÚÑ]/.test(v) || /[^\w\s]/.test(v); }
    };

    function revisar() {
      var v = campo.value;
      var cumplidas = 0;
      reglas.forEach(function (li) {
        var prueba = PRUEBAS[li.dataset.regla];
        var ok = prueba ? prueba(v) : false;
        li.classList.toggle('ok', ok);
        if (ok) cumplidas++;
      });

      var nivel = v.length === 0 ? 0 : cumplidas <= 2 ? 1 : cumplidas === 3 ? 2 : 3;
      var nombre = ['', 'floja', 'media', 'fuerte'][nivel];

      if (medidor) {
        medidor.className = 'meter ' + nombre;
        medidor.querySelectorAll('span').forEach(function (s, i) {
          s.classList.toggle('on', i < nivel);
        });
      }
      if (rotulo) {
        rotulo.className = 'fuerza ' + nombre;
        rotulo.querySelector('b').textContent =
          v.length === 0 ? '—' : ['', 'Floja', 'Media', 'Fuerte'][nivel];
      }
    }

    campo.addEventListener('input', revisar);
    revisar();
  });

  /* ---------------------------------------------------------------------
     6. Las seis casillas del código

     El formulario trae un campo de texto normal, y este bloque lo reemplaza
     por las seis casillas: son más cómodas, pero no son imprescindibles. Sin
     JavaScript la pantalla funciona con el campo de texto, y en los dos
     casos lo que se envía es el mismo valor de seis dígitos.
     --------------------------------------------------------------------- */

  document.addEventListener('DOMContentLoaded', function () {
    var caja = document.querySelector('.pin');
    if (!caja) return;

    var campo = document.querySelector('[data-codigo-completo]');
    var casillas = Array.prototype.slice.call(caja.querySelectorAll('.pin-casilla'));
    var boton = document.querySelector('[data-validar]');

    /* El cambio de uno por otras: se hace aquí y no en el HTML para que la
       página sirva igual si este archivo no llega a cargar. */
    var simple = document.querySelector('[data-codigo-simple]');
    var grupo = document.querySelector('[data-codigo-casillas]');
    if (simple && grupo) {
      simple.hidden = true;
      grupo.hidden = false;
    }

    /* Si el campo venía con valor (por ejemplo, tras un error del
       servidor), se reparte entre las casillas. */
    if (campo && campo.value) {
      campo.value.replace(/\D/g, '').slice(0, casillas.length)
        .split('').forEach(function (d, i) { casillas[i].value = d; });
    }

    function juntar() {
      var valor = casillas.map(function (c) { return c.value; }).join('');
      if (campo) campo.value = valor;
      casillas.forEach(function (c) { c.classList.toggle('lleno', !!c.value); });
      if (boton) boton.disabled = valor.length !== casillas.length;
    }

    casillas.forEach(function (c, i) {
      c.addEventListener('input', function () {
        c.value = c.value.replace(/\D/g, '').slice(-1);
        if (c.value && i < casillas.length - 1) casillas[i + 1].focus();
        juntar();
      });
      c.addEventListener('keydown', function (e) {
        if (e.key === 'Backspace' && !c.value && i > 0) {
          casillas[i - 1].focus();
          casillas[i - 1].value = '';
          juntar();
          e.preventDefault();
        }
      });
      c.addEventListener('paste', function (e) {
        var texto = (e.clipboardData || window.clipboardData).getData('text').replace(/\D/g, '');
        if (!texto) return;
        e.preventDefault();
        casillas.forEach(function (x, j) { x.value = texto[j] || ''; });
        casillas[Math.min(texto.length, casillas.length) - 1].focus();
        juntar();
      });
    });

    juntar();
    if (casillas[0]) casillas[0].focus();
  });

  /* ---------------------------------------------------------------------
     7. El RUT que busca la ficha del solicitante

     Al salir del campo se consulta al servidor. Si la persona ya fue
     atendida, se completan los demás datos; el funcionario los confirma o
     los corrige. Sin JavaScript hay que escribirlos, y el servidor reutiliza
     la ficha igual, porque la busca por RUT al guardar.
     --------------------------------------------------------------------- */

  document.addEventListener('DOMContentLoaded', function () {
    var campo = document.querySelector('[data-buscar-rut]');
    if (!campo) return;

    /* El atributo trae la dirección de la consulta, que la pone Django con
       reverse(): así no hay una ruta escrita a mano en este archivo. */
    var url = campo.getAttribute('data-buscar-rut');
    if (!url) return;

    var estado = document.querySelector('[data-rut-estado]');
    var destinos = {
      nombre: document.querySelector('[data-rut-nombre]'),
      telefono: document.querySelector('[data-rut-telefono]'),
      territorio: document.querySelector('[data-rut-territorio]')
    };
    var ultimo = '';

    function avisar(texto, clase) {
      if (!estado) return;
      estado.textContent = texto;
      estado.className = 'help' + (clase ? ' ' + clase : '');
    }

    campo.addEventListener('blur', function () {
      var rut = campo.value.trim();
      if (!rut || rut === ultimo) return;
      ultimo = rut;

      avisar('Buscando…');
      fetch(url + '?rut=' + encodeURIComponent(rut), {
        headers: { 'X-Requested-With': 'fetch' }
      })
        .then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); })
        .then(function (d) {
          if (!d.valido) {
            avisar('Ese RUT no es válido: revisa el número y el dígito verificador.', 'malo');
            return;
          }
          if (!d.encontrado) {
            avisar('No está registrado: al guardar se crea su ficha.');
            return;
          }
          Object.keys(destinos).forEach(function (k) {
            if (!destinos[k] || !d[k]) return;
            destinos[k].value = d[k];
            /* El territorio es un selector: se avisa el cambio para que el
               campo visible muestre el territorio encontrado. */
            if (destinos[k].tagName === 'SELECT') {
              destinos[k].dispatchEvent(new Event('change', { bubbles: true }));
            }
          });
          avisar('Ficha encontrada · ' + d.atenciones +
                 (d.atenciones === 1 ? ' atención previa' : ' atenciones previas'), 'bueno');
        })
        .catch(function () {
          /* Si la consulta falla, no se estorba: los campos se escriben a
             mano y el servidor reutiliza la ficha de todas formas. */
          avisar('No se pudo consultar ahora. Escribe los datos y continúa.');
        });
    });
  });

  /* ---------------------------------------------------------------------
     7b. Espera entre reenvíos del código

     Igual que arriba: esto solo muestra la espera. Quien la aplica es el
     servidor, que rechaza el reenvío anticipado aunque el botón esté
     habilitado.
     --------------------------------------------------------------------- */

  document.addEventListener('DOMContentLoaded', function () {
    var boton = document.querySelector('[data-reenviar]');
    if (!boton) return;

    var restan = parseInt(boton.dataset.reenviar, 10) || 0;
    var reloj = document.querySelector('[data-reenviar-reloj]');
    if (restan <= 0) return;

    boton.disabled = true;
    (function tic() {
      if (restan <= 0) {
        boton.disabled = false;
        if (reloj && reloj.parentNode) reloj.parentNode.remove();
        return;
      }
      if (reloj) reloj.textContent = restan;
      restan--;
      setTimeout(tic, 1000);
    })();
  });

  /* ---------------------------------------------------------------------
     8. Cuenta atrás de vigencia del código
     --------------------------------------------------------------------- */

  document.addEventListener('DOMContentLoaded', function () {
    var caja = document.querySelector('[data-cuenta]');
    if (!caja) return;

    var restan = parseInt(caja.dataset.cuenta, 10) || 0;
    var reloj = caja.querySelector('.reloj');

    (function tic() {
      if (restan <= 0) {
        caja.classList.add('vencida');
        caja.textContent = 'El código caducó. Pide uno nuevo para continuar.';
        return;
      }
      reloj.textContent = Math.floor(restan / 60) + ':' + String(restan % 60).padStart(2, '0');
      caja.classList.toggle('poco', restan <= 60);
      restan--;
      setTimeout(tic, 1000);
    })();
  });

  /* ---------------------------------------------------------------------
     9. Meta y ponderador sugeridos al crear una meta

     Al elegir el ítem, propone la meta y el ponderador que el ítem trae en
     el catálogo. Solo escribe en los campos que la persona no ha tocado:
     lo que ya escribió a mano no se reemplaza. La validación del 100 % por
     cargo la sigue haciendo el servidor.
     --------------------------------------------------------------------- */

  document.addEventListener('DOMContentLoaded', function () {
    var datos = document.getElementById('sgr-sugeridos');
    var item = document.querySelector('select[name="item"]');
    if (!datos || !item) return;

    var sugeridos = JSON.parse(datos.textContent);
    var campos = ['meta', 'ponderador'].map(function (nombre) {
      return document.querySelector('input[name="' + nombre + '"]');
    }).filter(Boolean);

    campos.forEach(function (campo) {
      if (campo.value === '') campo.dataset.propuesto = '1';
      campo.addEventListener('input', function () { delete campo.dataset.propuesto; });
    });

    item.addEventListener('change', function () {
      var valores = sugeridos[item.value];
      campos.forEach(function (campo) {
        if (!campo.dataset.propuesto) return;
        campo.value = valores ? valores[campo.name] : '';
      });
    });
  });
})();

"""
El patrón de mantenedor, una sola vez.

Los seis mantenedores del SGR hacen lo mismo: listar con búsqueda, filtros,
orden y paginador; exportar lo que está filtrado; crear, editar y consultar;
y activar o desactivar respetando las relaciones protegidas. Aquí está ese
comportamiento, y cada entidad solo declara qué columnas tiene y por dónde
se busca.

Cómo se traduce desde la maqueta
--------------------------------
La maqueta estática guardaba el estado del listado en la barra de
direcciones: ``?q=&zona=&estado=&orden=&dir=&p=&tam=``. Son los mismos
parámetros GET que lee esta vista, así que la traducción es directa:

    filtrar()  ->  _buscar() y _filtrar(), que arman el queryset
    ordenar()  ->  _ordenar(), que arma el order_by
    paginar()  ->  el Paginator de Django, vía ListView
    pintar()   ->  la plantilla comun/mantenedor_lista.html

Sobre la búsqueda sin tildes: la hace el motor, no Python. Las tablas se
crean con ``utf8mb4_unicode_ci``, una colación que compara ignorando
mayúsculas y acentos, así que ``nombre__icontains="companias"`` encuentra
«Las Compañías». Por eso la colación de la base no es un detalle.
"""

from urllib.parse import urlencode

from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.html import conditional_escape, format_html
from django.utils.safestring import mark_safe
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from comun.excel import libro_de_listado
from comun.navegacion import desde_formulario
from comun.permisos import RequierePermiso, perfil_de, tiene_permiso
from comun.resultado import anunciar

TAMANOS = [10, 25, 50]

#: Cuántos campos cambiados se escriben en la auditoría. Un volcado completo
#: del registro no se lee, y una auditoría que no se lee no sirve.
CAMPOS_AUDITADOS = 6


def auditar(request, accion, obj, *, entidad, antes="", despues="", detalle=""):
    """
    Deja el evento en la auditoría, sin dejar caer la operación si falla.

    Se importa aquí dentro y no arriba porque ``comun.auditoria`` necesita
    los modelos, y este módulo lo cargan las aplicaciones mientras Django
    todavía está construyendo el registro de modelos.
    """
    from comun.auditoria import registrar

    return registrar(request, accion, entidad=entidad, objeto=obj,
                     antes=antes, despues=despues, detalle=detalle)


def _resumen_auditoria(form, iniciales=False):
    """
    Los campos que cambiaron, en una línea.

    Con ``iniciales`` devuelve los valores que tenían antes de guardar; sin
    él, los que quedaron. Solo los campos que el formulario marcó como
    cambiados: anotar los treinta campos de un registro porque se corrigió
    una coma convierte la auditoría en ruido.
    """
    cambiados = list(getattr(form, "changed_data", []))[:CAMPOS_AUDITADOS]
    if not cambiados:
        return ""
    origen = form.initial if iniciales else getattr(form, "cleaned_data", {})
    partes = []
    for campo in cambiados:
        valor = origen.get(campo, None)
        if valor is None or valor == "":
            valor = "—"
        texto = str(valor)
        partes.append(f"{campo}: {texto[:60]}")
    sobran = len(getattr(form, "changed_data", [])) - len(cambiados)
    if sobran > 0:
        partes.append(f"y {sobran} campo{'s' if sobran > 1 else ''} más")
    return " · ".join(partes)


# =========================================================================
# Alcance por delegación
# =========================================================================


class AlcanceDelegacion:
    """
    Limita un mantenedor a las delegaciones que el perfil autoriza.

    El permiso dice *qué* puede hacer una persona; el alcance de su rol dice
    *sobre qué delegaciones*. Tener el permiso de gestionar usuarios no
    significa poder gestionar los de todas las delegaciones: solo un rol con
    alcance «todas» ve el sistema completo.

    Por qué está en el motor y no en cada vista
    ------------------------------------------
    Porque hay cinco caminos hasta un registro —listado, ficha, edición,
    exportación y cambio de estado— y basta olvidarlo en uno para que el
    dato se escape. Aquí el filtro se aplica en los cinco, y cada mantenedor
    solo declara por dónde se llega a la delegación:

        campo_delegacion = "pk"             en el mantenedor de Delegaciones
        campo_delegacion = "delegacion_id"  en el de Usuarios

    Los catálogos —roles, ítems, tipos, subatenciones— son del municipio
    entero, no de una delegación, así que no declaran nada y se ven completos.

    Un registro fuera del alcance no da «prohibido» sino «no existe»: decir
    «existe pero no puedes verlo» ya es filtrar información.
    """

    campo_delegacion = None

    def delegaciones_permitidas(self):
        """
        Los identificadores de delegación que esta persona puede ver.

        ``None`` significa «sin límite», que es el caso del superusuario y de
        los roles con alcance «todas».
        """
        usuario = getattr(self.request, "user", None)
        if usuario is None or getattr(usuario, "is_superuser", False):
            return None

        perfil = perfil_de(usuario)
        if perfil is None:
            return None

        from organizacion.models import Rol

        if perfil.rol.alcance == Rol.Alcance.TODAS:
            return None
        return list(perfil.delegaciones_visibles().values_list("pk", flat=True))

    def limitar(self, consulta):
        """Aplica el límite a un queryset, si corresponde."""
        if not self.campo_delegacion:
            return consulta
        permitidas = self.delegaciones_permitidas()
        if permitidas is None:
            return consulta
        return consulta.filter(**{f"{self.campo_delegacion}__in": permitidas})

    def dentro_del_alcance(self, obj):
        """True si ese registro concreto está dentro del alcance."""
        if not self.campo_delegacion:
            return True
        permitidas = self.delegaciones_permitidas()
        if permitidas is None:
            return True
        return getattr(obj, self.campo_delegacion, None) in permitidas


# =========================================================================
# Declaraciones que usa cada mantenedor
# =========================================================================


class Columna:
    """Una columna del listado.

    ``campo`` es el nombre del atributo del modelo y, salvo que se diga otra
    cosa, también por el que se ordena. ``celda`` permite dibujar algo más
    que el valor crudo: recibe el objeto y devuelve HTML.
    """

    def __init__(self, campo, titulo, *, orden=None, alineado="",
                 clase="", celda=None, valor=None):
        self.campo = campo
        self.titulo = titulo
        self.orden = campo if orden is None else orden
        self.alineado = alineado
        self.clase = clase
        self._celda = celda
        self._valor = valor

    @property
    def ordenable(self):
        return bool(self.orden)

    def valor(self, obj):
        """El dato en bruto. Es lo que va al Excel."""
        if self._valor:
            return self._valor(obj)
        dato = obj
        for parte in self.campo.split("__"):
            dato = getattr(dato, parte, "")
            if dato is None:
                return ""
        return dato

    def html(self, obj):
        """Lo que se ve en la tabla."""
        if self._celda:
            return mark_safe(self._celda(obj))
        return conditional_escape(self.valor(obj))

    @property
    def clases(self):
        return " ".join(x for x in [self.alineado, self.clase] if x)


class Filtro:
    """Un desplegable de la barra de filtros.

    ``opciones`` es una lista de pares (valor, texto). ``consulta`` recibe el
    valor elegido y devuelve un Q; si no se entrega, se filtra por igualdad
    sobre el campo del mismo nombre.
    """

    def __init__(self, clave, titulo, opciones=None, *, consulta=None,
                 vacio="Todas", campo=None):
        self.clave = clave
        self.titulo = titulo
        self._opciones = opciones or []
        self._consulta = consulta
        self.vacio = vacio
        self.campo = campo or clave

    def opciones(self):
        return self._opciones() if callable(self._opciones) else self._opciones

    def q(self, valor):
        if self._consulta:
            return self._consulta(valor)
        return Q(**{self.campo: valor})

    def rotulo(self, valor):
        for clave, texto in self.opciones():
            if str(clave) == str(valor):
                return texto
        return valor


def filtro_estado(femenino=False):
    """El filtro activas/inactivas, que todos los mantenedores comparten."""
    a = "a" if femenino else "o"
    return Filtro(
        "estado", "Estado",
        [("activos", f"Solo activ{a}s"), ("inactivos", f"Solo inactiv{a}s")],
        consulta=lambda v: Q(activo=(v == "activos")),
        vacio="Todos" if not femenino else "Todas",
    )


# =========================================================================
# Listado
# =========================================================================


class ListaMantenedor(RequierePermiso, AlcanceDelegacion, ListView):
    """Listado con búsqueda, filtros, orden, paginador y exportación."""

    template_name = "comun/mantenedor_lista.html"
    context_object_name = "filas"
    # La maqueta usaba ?p= para la página; se mantiene para que las
    # direcciones de una y otra sean las mismas.
    page_kwarg = "p"

    # --- lo que declara cada mantenedor ---
    titulo = ""
    bajada = ""
    singular = "registro"
    plural = "registros"
    genero = "el"          # «el» o «la», para redactar los mensajes
    placeholder = "Buscar"
    columnas = []
    filtros = []
    busca = []
    orden_inicial = "codigo"
    excel_columnas = None   # si es None, se exportan las columnas visibles
    nota = ""
    url_lista = ""
    url_nueva = ""
    url_editar = ""
    url_detalle = ""
    url_estado = ""
    rotulo_nuevo = "Nuevo"
    menu = ""               # qué entrada del menú lateral se marca

    # --- consulta --------------------------------------------------------

    def base_queryset(self):
        """El universo de registros antes de filtrar. Se redefine cuando el
        listado tiene que limitarse a la delegación activa."""
        return self.model._default_manager.all()

    def get_queryset(self):
        # El límite por delegación va primero y envuelve a todo lo demás: la
        # búsqueda, los filtros y la exportación trabajan sobre lo que esta
        # persona puede ver, nunca sobre la tabla completa.
        consulta = self.limitar(self.base_queryset())
        consulta = self._buscar(consulta)
        consulta = self._filtrar(consulta)
        return self._ordenar(consulta)

    def _buscar(self, consulta):
        termino = (self.request.GET.get("q") or "").strip()
        if not termino or not self.busca:
            return consulta
        condicion = Q()
        for campo in self.busca:
            condicion |= Q(**{f"{campo}__icontains": termino})
        return consulta.filter(condicion)

    def _filtrar(self, consulta):
        for filtro in self.filtros:
            valor = (self.request.GET.get(filtro.clave) or "").strip()
            if valor:
                consulta = consulta.filter(filtro.q(valor))
        return consulta

    def _ordenar(self, consulta):
        campo = self.request.GET.get("orden") or self.orden_inicial
        permitidos = {c.orden for c in self.columnas if c.ordenable}
        if campo not in permitidos:
            campo = self.orden_inicial
        if self.request.GET.get("dir") == "desc":
            campo = f"-{campo}"
        return consulta.order_by(campo)

    def get_paginate_by(self, queryset):
        try:
            tam = int(self.request.GET.get("tam", 10))
        except (TypeError, ValueError):
            tam = 10
        return tam if tam in TAMANOS else 10

    # --- exportación -----------------------------------------------------

    def get(self, request, *args, **kwargs):
        if request.GET.get("export") == "excel":
            return self._exportar()
        return super().get(request, *args, **kwargs)

    def _exportar(self):
        """
        Exporta lo que está filtrado, no la tabla completa.

        Usa ``get_queryset()``, el mismo del listado, así que es imposible
        que el archivo y la pantalla muestren cosas distintas.
        """
        columnas = self.excel_columnas or self.columnas
        filas = list(self.get_queryset())
        return libro_de_listado(
            titulo=f"Mantenedor de {self.plural}",
            filtro=self.describir_filtros() or "sin filtros",
            columnas=columnas,
            filas=filas,
            archivo=f"SGR_{self.plural.replace(' ', '_')}",
        )

    # --- apoyo para la plantilla -----------------------------------------

    def describir_filtros(self):
        partes = []
        termino = (self.request.GET.get("q") or "").strip()
        if termino:
            partes.append(f"búsqueda «{termino}»")
        for filtro in self.filtros:
            valor = (self.request.GET.get(filtro.clave) or "").strip()
            if valor:
                partes.append(f"{filtro.titulo.lower()}: {filtro.rotulo(valor)}")
        return " · ".join(partes)

    def _cola(self, **cambios):
        """La dirección actual con algunos parámetros cambiados."""
        datos = {
            clave: valor
            for clave, valor in self.request.GET.items()
            if valor and clave not in {"export"}
        }
        datos.update({k: v for k, v in cambios.items() if v not in (None, "")})
        for clave, valor in cambios.items():
            if valor in (None, "") and clave in datos:
                del datos[clave]
        return urlencode(datos)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        orden = self.request.GET.get("orden") or self.orden_inicial
        direccion = "desc" if self.request.GET.get("dir") == "desc" else "asc"

        encabezados = []
        for columna in self.columnas:
            actual = columna.ordenable and columna.orden == orden
            encabezados.append({
                "titulo": columna.titulo,
                "clases": columna.clases,
                "ordenable": columna.ordenable,
                "aria": ("ascending" if direccion == "asc" else "descending") if actual else "",
                "cola": self._cola(
                    orden=columna.orden,
                    dir="desc" if (actual and direccion == "asc") else None,
                    p=None,
                ) if columna.ordenable else "",
            })

        filas = []
        for obj in ctx["filas"]:
            filas.append({
                "obj": obj,
                "clase": "" if getattr(obj, "activo", True) else "off",
                "celdas": [
                    {"html": c.html(obj), "clases": c.clases} for c in self.columnas
                ],
            })

        filtros = []
        for filtro in self.filtros:
            filtros.append({
                "clave": filtro.clave,
                "titulo": filtro.titulo,
                "vacio": filtro.vacio,
                "elegido": self.request.GET.get(filtro.clave, ""),
                "opciones": filtro.opciones(),
            })

        ctx.update({
            "titulo": self.titulo,
            "bajada": self.bajada,
            "singular": self.singular,
            "plural": self.plural,
            "genero": self.genero,
            "placeholder": self.placeholder,
            "nota": self.nota,
            "encabezados": encabezados,
            "cuerpo": filas,
            "filtros": filtros,
            "termino": self.request.GET.get("q", ""),
            "descripcion_filtros": self.describir_filtros(),
            "tamanos": TAMANOS,
            "tam": self.get_paginate_by(None),
            "cola_sin_pagina": self._cola(p=None),
            "cola_exportar": self._cola(export="excel", p=None),
            "url_lista": self.url_lista,
            "url_nueva": self.url_nueva,
            "url_editar": self.url_editar,
            "url_detalle": self.url_detalle,
            "url_estado": self.url_estado,
            "rotulo_nuevo": self.rotulo_nuevo,
            "menu": self.menu,
            # «¿Hay datos?» también se pregunta dentro del alcance: si esta
            # persona no ve ninguno, el estado vacío correcto es «todavía no
            # hay», no «sin coincidencias».
            "hay_datos": self.limitar(self.base_queryset()).exists(),
        })
        return ctx


# =========================================================================
# Formularios
# =========================================================================


class _FormMantenedor(RequierePermiso, AlcanceDelegacion):
    """Lo común entre crear y editar."""

    template_name = "comun/mantenedor_form.html"
    singular = "registro"
    plural = "registros"
    genero = "el"
    url_lista = ""
    url_detalle = ""
    menu = ""
    lateral = "comun/_lateral_vacio.html"
    secciones = []          # [(número, título, bajada, [nombres de campo])]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        formulario = ctx["form"]

        bloques = []
        for numero, (titulo, bajada, campos) in enumerate(self.secciones, start=1):
            bloques.append({
                "numero": numero,
                "titulo": titulo,
                "bajada": bajada,
                "campos": [formulario[nombre] for nombre in campos if nombre in formulario.fields],
            })

        ctx.update({
            "singular": self.singular,
            "plural": self.plural,
            "genero": self.genero,
            "url_lista": self.url_lista,
            "url_detalle": self.url_detalle,
            "menu": self.menu,
            "lateral": self.lateral,
            "secciones": bloques,
            "es_nuevo": isinstance(self, CrearMantenedor),
        })
        return ctx

    def get_queryset(self):
        """
        Editar solo lo que está dentro del alcance.

        Al crear no se usa —no hay registro que buscar—; al editar, un pk de
        otra delegación no se encuentra y la vista responde 404.
        """
        return self.limitar(super().get_queryset())

    def get_success_url(self):
        return reverse(self.url_lista)


class CrearMantenedor(_FormMantenedor, CreateView):
    def form_valid(self, form):
        # El aviso se prepara DESPUÉS de super(), que es quien guarda: si
        # guardar fallara, no habría nada que anunciar.
        respuesta = super().form_valid(form)

        # La auditoría se escribe desde el motor y no desde cada vista: así
        # los seis mantenedores quedan cubiertos de una vez, y ninguno se
        # olvida por haberse construido después.
        auditar(self.request, "crear", self.object,
                entidad=self.model._meta.verbose_name.capitalize(),
                despues=_resumen_auditoria(form))

        vocal = "a" if self.genero == "la" else "o"
        anunciar(
            self.request,
            f"{self.singular.capitalize()} cread{vocal}",
            f"«{self.object}» quedó registrad{vocal} con el código "
            f"{getattr(self.object, 'codigo', '')} y ya aparece en los "
            "selectores del sistema.",
            acciones=[
                ("Ver el listado", reverse(self.url_lista)),
                ("Ver la ficha", reverse(self.url_detalle, args=[self.object.pk]))
                if self.url_detalle else None,
            ],
        )
        return respuesta


class EditarMantenedor(_FormMantenedor, UpdateView):
    def form_valid(self, form):
        # El «antes» se arma con los valores que el formulario trae marcados
        # como cambiados, y hay que leerlos ANTES de guardar: después ya no
        # existen. Es la mitad del «antes y después» que pide INT-03.
        antes = _resumen_auditoria(form, iniciales=True)
        respuesta = super().form_valid(form)
        auditar(self.request, "editar", self.object,
                entidad=self.model._meta.verbose_name.capitalize(),
                antes=antes, despues=_resumen_auditoria(form))
        anunciar(
            self.request,
            "Cambios guardados",
            f"Se actualizó «{self.object}».",
            acciones=[("Volver al listado", reverse(self.url_lista))],
        )
        return respuesta


class DetalleMantenedor(RequierePermiso, AlcanceDelegacion, DetailView):
    template_name = "comun/mantenedor_detalle.html"
    context_object_name = "obj"
    singular = "registro"
    plural = "registros"
    genero = "el"
    url_lista = ""
    url_editar = ""
    url_estado = ""
    menu = ""
    campos = []     # [(etiqueta, nombre_o_llamable, {"ancho": bool, "mono": bool})]
    kpis = []       # [(etiqueta, llamable, pie)]
    pie = ""

    def get_queryset(self):
        """La ficha de un registro fuera del alcance no existe: 404."""
        return self.limitar(super().get_queryset())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj = ctx["obj"]

        datos = []
        for etiqueta, origen, *resto in self.campos:
            extra = resto[0] if resto else {}
            if callable(origen):
                valor = origen(obj)
            else:
                # Si el campo tiene choices, se muestra la etiqueta legible.
                mostrar = getattr(obj, f"get_{origen}_display", None)
                valor = mostrar() if callable(mostrar) else getattr(obj, origen, "")
            datos.append({
                "etiqueta": etiqueta,
                "valor": mark_safe(valor) if extra.get("html") else valor,
                "ancho": extra.get("ancho", False),
                "mono": extra.get("mono", False),
            })

        tarjetas = [
            {"etiqueta": e, "valor": f(obj), "pie": mark_safe(p)}
            for e, f, p in self.kpis
        ]

        ctx.update({
            "singular": self.singular,
            "plural": self.plural,
            "genero": self.genero,
            "url_lista": self.url_lista,
            "url_editar": self.url_editar,
            "url_estado": self.url_estado,
            "menu": self.menu,
            "datos": datos,
            "kpis": tarjetas,
            "pie": self.pie,
            "motivo_bloqueo": obj.motivo_bloqueo() if hasattr(obj, "motivo_bloqueo") else "",
        })
        return ctx


# =========================================================================
# Activar y desactivar
# =========================================================================


class CambiarEstado(AlcanceDelegacion, View):
    """
    Activa o desactiva un registro.

    Solo responde a POST: cambiar el estado modifica datos, y eso no se hace
    con un enlace que cualquiera pueda abrir desde el historial. El
    formulario que lo invoca lleva su token CSRF.

    Antes de desactivar se consulta ``motivo_bloqueo()`` del propio modelo:
    es la clase la que sabe qué relaciones la protegen.

    Es el único de los cinco caminos que **escribe**, así que además del
    permiso comprueba el alcance: un pk de otra delegación se trata como
    inexistente.
    """

    model = None
    permiso = None
    url_lista = ""
    singular = "registro"
    genero = "el"

    def post(self, request, pk):
        if not request.user.is_authenticated:
            from comun.permisos import redirect_al_login

            return redirect_al_login(request)
        if self.permiso and not tiene_permiso(request.user, self.permiso):
            raise PermissionDenied("No tienes permiso para cambiar ese estado.")

        obj = get_object_or_404(self.limitar(self.model._default_manager.all()), pk=pk)
        activar = request.POST.get("activar") == "1"
        vocal = "a" if self.genero == "la" else "o"

        if not activar:
            motivo = obj.motivo_bloqueo() if hasattr(obj, "motivo_bloqueo") else ""
            if motivo:
                # La operación NO se hizo, así que el aviso es de error. Que
                # una restricción impida continuar no es un éxito.
                anunciar(
                    request,
                    f"No se puede desactivar «{obj}»",
                    motivo,
                    icono="error",
                )
                return self._volver(request)

        antes = "activo" if obj.activo else "inactivo"
        obj.activo = activar
        if hasattr(obj, "desactivada"):
            obj.desactivada = None if activar else timezone.localdate()
            obj.save(update_fields=["activo", "desactivada"])
        else:
            obj.save(update_fields=["activo"])

        auditar(request, "estado", obj,
                entidad=self.model._meta.verbose_name.capitalize(),
                antes=antes, despues="activo" if activar else "inactivo")

        estado = "activ" + vocal if activar else "desactivad" + vocal
        anunciar(
            request,
            f"{self.singular.capitalize()} {estado}",
            f"«{obj}» quedó {estado}. "
            + ("Vuelve a ofrecerse en los formularios."
               if activar else
               "Deja de ofrecerse en los registros nuevos; lo ya registrado se conserva."),
        )
        return self._volver(request)

    def _volver(self, request):
        """
        De vuelta al listado del que se venía, con su página y sus filtros.

        El destino viene en un campo oculto del formulario, y por eso se
        valida: un valor de formulario que llega sin comprobar a un
        ``redirect()`` es una redirección abierta, y una redirección abierta
        en un sistema con sesión es el primer paso de una suplantación —el
        enlace es de este sistema, el dominio es el correcto, y la pantalla
        de contraseña en la que termina no lo es—. Que el campo esté oculto
        no cambia nada: es parte de la página, y la página la controla el
        navegador.
        """
        return HttpResponseRedirect(desde_formulario(request, self.url_lista))


# =========================================================================
# Utilidades de presentación
# =========================================================================


def chip_estado(obj, femenino=False):
    """El distintivo verde o gris del estado, igual en los seis listados."""
    a = "a" if femenino else "o"
    if obj.activo:
        return format_html(
            '<span class="chip ok">'
            '<svg class="i" width="14" height="14" viewBox="0 0 24 24" fill="none" '
            'stroke="currentColor" stroke-width="2.2" stroke-linecap="round" '
            'stroke-linejoin="round" aria-hidden="true"><path d="m5 12.5 4.5 4.5L19 7.5"/>'
            "</svg>Activ{}</span>", a,
        )
    return format_html(
        '<span class="chip off"><span class="t">Inactiv{}</span></span>', a
    )


def enlace_nombre(obj, url_detalle, *, extra="", femenino=False):
    """El nombre como enlace a la ficha, con una segunda línea opcional."""
    cuerpo = format_html(
        '<a class="link" href="{}">{}</a>',
        reverse(url_detalle, args=[obj.pk]),
        obj.nombre,
    )
    if not obj.activo and getattr(obj, "desactivada", None):
        extra = format_html(
            '<span class="t2">Desactivad{} el {}</span>',
            "a" if femenino else "o",
            obj.desactivada.strftime("%d-%m-%Y"),
        )
    elif extra:
        extra = mark_safe(extra)
    return cuerpo + (extra or "")


# La columna de acciones no se arma aquí: lleva un formulario POST y su token
# CSRF, y el token solo puede salir de la plantilla. Lo dibuja
# comun/mantenedor_lista.html a partir de url_editar y url_estado.

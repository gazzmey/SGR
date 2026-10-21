"""
Las dos pantallas de resultado: la propia y la de la delegación.

Son la misma información vista desde dos lugares. «Mi resultado» responde
«cómo voy»; el tablero responde «cómo va la delegación». Las dos usan el
mismo motor, así que no pueden contradecirse: si el tablero dice que alguien
lleva 62 %, su propia pantalla dice 62 %. El caso TAB-01 comprueba
exactamente esa coincidencia.

Lo que estas pantallas **no** hacen
-----------------------------------
No emiten juicios ni decisiones. Muestran el cálculo, de dónde sale y con
qué reglas, y nada más. El requisito RF-031 lo pide explícitamente —«no
emite decisiones automáticas laborales»— y es la razón por la que no hay
ninguna etiqueta del tipo «bajo rendimiento» en ninguna parte: el semáforo
dice «atrasado» respecto de una fecha, que es un hecho, no una valoración
de la persona.
"""

from django.core.exceptions import PermissionDenied
from django.shortcuts import render

from comun import permisos as P
from comun.contexto import delegacion_activa
from comun.excel import libro_de_listado
from comun.permisos import redirect_al_login, tiene_permiso
from gestion import calculo as C
from gestion import tablero as T
from organizacion.models import Delegacion


def _exigir(request, permiso, queja):
    if not request.user.is_authenticated:
        return redirect_al_login(request)
    if permiso and not tiene_permiso(request.user, permiso):
        raise PermissionDenied(queja)
    return None


def _contexto_comun(request):
    """El período elegido y la lista para el selector."""
    periodo = T.periodo_elegido(request)
    return {
        "periodo": periodo,
        "periodos": list(T.periodos_visibles()),
    }


# =========================================================================
# Mi resultado
# =========================================================================


def mi_resultado(request):
    """
    Cómo va quien está mirando, y de dónde sale ese número (RF-028, RF-030).

    No lleva permiso propio: cualquiera que tenga sesión puede ver **su**
    resultado. Lo que sí tiene es alcance: la consulta se arma con su propio
    perfil, así que no hay forma de pedir el de otra persona.
    """
    desvio = _exigir(request, None, "")
    if desvio:
        return desvio

    datos = _contexto_comun(request)
    periodo = datos["periodo"]
    perfil = P.perfil_de(request.user)

    if perfil is None or periodo is None:
        return render(request, "gestion/mi_resultado.html", {
            "menu": "mi_resultado",
            **datos,
            "sin_datos": (
                "Todavía no hay un período configurado."
                if periodo is None else
                "Tu cuenta no tiene perfil en el sistema, así que no hay "
                "metas con las que medirte. Es lo normal en un superusuario."
            ),
        })

    resultado = C.de_perfil(perfil, periodo)
    return render(request, "gestion/mi_resultado.html", {
        "menu": "mi_resultado",
        **datos,
        "perfil": perfil,
        "res": resultado,
        "resumen": T.resumen_actividades(perfil, periodo),
        "pendientes": T.pendientes_de(perfil, periodo),
        "recientes": T.recientes_de(perfil, periodo),
        "sin_datos": "",
    })


# =========================================================================
# Tablero de delegación
# =========================================================================


def tablero(request):
    """
    El resultado de cada persona de la delegación (RF-029, RF-031).

    La delegación es la activa de la sesión, que ya está comprobada contra
    las que el perfil autoriza. Se puede cambiar con ``?delegacion=``, y ese
    valor se vuelve a comprobar aquí: aceptarlo sin más sería dejar que
    cualquiera leyera el resultado de una delegación ajena escribiendo un
    número en la dirección.
    """
    desvio = _exigir(request, P.VER_TABLERO,
                     "No tienes permiso para ver el tablero de delegación.")
    if desvio:
        return desvio

    datos = _contexto_comun(request)
    periodo = datos["periodo"]
    perfil = P.perfil_de(request.user)

    if perfil is not None:
        permitidas = perfil.delegaciones_visibles()
    else:
        permitidas = Delegacion.objects.filter(activo=True)

    pedida = request.GET.get("delegacion")
    delegacion = None
    if pedida:
        delegacion = permitidas.filter(pk=pedida).first()
        if delegacion is None:
            raise PermissionDenied(
                "Esa delegación no está entre las que tu perfil autoriza."
            )
    if delegacion is None:
        delegacion = delegacion_activa(request) or permitidas.first()

    if periodo is None or delegacion is None:
        return render(request, "gestion/tablero.html", {
            "menu": "tablero", **datos,
            "sin_datos": ("Todavía no hay un período configurado."
                          if periodo is None else
                          "Tu perfil no tiene delegaciones autorizadas."),
        })

    resultado = C.de_delegacion(delegacion, periodo)

    if request.GET.get("formato") == "excel":
        return _excel(resultado)

    return render(request, "gestion/tablero.html", {
        "menu": "tablero", **datos,
        "delegacion": delegacion,
        "delegaciones": list(permitidas),
        "res": resultado,
        "uso": T.uso_de(resultado),
        "cola": T.evidencias_por_revisar(delegacion, periodo),
        # El indicador colectivo de la agenda: realizado, no realizado y si
        # alcanza el umbral. Es el lote CAL-C, y está acá porque «cómo va la
        # delegación» incluye los compromisos con la comunidad y no solo las
        # metas personales.
        "agenda": C.logro_agenda(periodo, delegacion),
        "sin_datos": "",
    })


class _Col:
    """
    Una columna de la exportación.

    El exportador de ``comun.excel`` espera objetos con ``titulo`` y
    ``valor(fila)``, que es lo que usan los mantenedores. Aquí las filas no
    son registros del modelo sino pares (perfil, resultado), así que se
    envuelven en esto en vez de duplicar el exportador.
    """

    def __init__(self, titulo, leer, ancho=24):
        self.titulo = titulo
        self._leer = leer
        self.ancho = ancho

    def valor(self, fila):
        return self._leer(*fila)


def _excel(resultado):
    """El tablero en una planilla, con las mismas cifras que la pantalla."""
    columnas = [
        _Col("Funcionario", lambda p, r: p.nombre, ancho=28),
        _Col("Cargo", lambda p, r: (p.cargo_asignado.nombre
                                    if p.cargo_asignado else "Sin cargo"), ancho=26),
        _Col("Ítems medidos", lambda p, r: r.items_medidos, ancho=14),
        _Col("Ítems al umbral", lambda p, r: r.items_alcanzados, ancho=14),
        _Col("Avance %", lambda p, r: (round(r.avance, 2) if r.definido
                                       else "Indefinido"), ancho=12),
        _Col("Esperado %", lambda p, r: (round(r.esperado, 2)
                                         if r.esperado is not None else ""), ancho=12),
        _Col("Semáforo", lambda p, r: r.semaforo_texto, ancho=14),
        _Col("Observación", lambda p, r: r.motivo_indefinido, ancho=50),
    ]
    return libro_de_listado(
        titulo="Tablero de %s · %s" % (resultado.delegacion.nombre,
                                       resultado.periodo.nombre),
        filtro="%s · al %s · %s" % (
            resultado.periodo.nombre,
            resultado.al_dia.strftime("%d-%m-%Y"),
            resultado.regla.rotulo,
        ),
        columnas=columnas,
        filas=list(resultado.personas),
        archivo="tablero_%s_%s" % (resultado.delegacion.codigo,
                                   resultado.periodo.codigo),
    )

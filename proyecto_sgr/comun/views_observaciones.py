"""
Escribir y consultar observaciones (HU-24, CU-63).

Escribir pide poder abrir el registro: es la misma comprobación de su ficha.
La página de observaciones recientes muestra solo las de registros que la
persona puede abrir, así que nadie se entera por aquí de lo que no vería en
la ficha.
"""

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from comun import observaciones as O
from comun.auditoria import registrar
from comun.models import EventoAuditoria, Observacion
from comun.resultado import anunciar

LARGO_MINIMO = 3
LARGO_MAXIMO = 2000


@require_POST
@login_required
def nueva(request):
    tipo = request.POST.get("tipo", "")
    objeto_id = request.POST.get("objeto", "")
    if tipo not in O.TIPOS or not objeto_id.isdigit():
        raise Http404("Ese registro no existe.")
    obj = O.registro(tipo, int(objeto_id))
    if obj is None:
        raise Http404("Ese registro no existe.")
    if not O.puede(request.user, tipo, obj):
        raise PermissionDenied("No puedes ver ese registro, así que tampoco comentarlo.")

    destino = O.url_de(tipo, obj) + "#observaciones"
    texto = (request.POST.get("texto") or "").strip()
    if len(texto) < LARGO_MINIMO:
        anunciar(request, "La observación está vacía",
                 "Escribe la consulta o el comentario antes de enviarlo.", icono="warning")
        return redirect(destino)
    if len(texto) > LARGO_MAXIMO:
        anunciar(request, "La observación es muy larga",
                 f"El máximo es de {LARGO_MAXIMO} caracteres; escribiste {len(texto)}.",
                 icono="warning")
        return redirect(destino)

    definicion = O.TIPOS[tipo]
    observacion = Observacion.objects.create(
        tipo=tipo, objeto_id=obj.pk, objeto_texto=definicion["texto"](obj)[:200],
        delegacion_id=definicion["delegacion"](obj), autor=request.user, texto=texto,
    )
    # CU-63 incluye «registrar la trazabilidad»: queda en la auditoría con
    # una parte del texto, para reconstruir quién comentó qué.
    registrar(request, EventoAuditoria.Accion.CREAR, entidad="Observación",
              objeto=observacion, objeto_texto=observacion.objeto_texto,
              despues=texto[:200])
    anunciar(request, "Observación enviada",
             "Queda en la conversación del registro, con tu nombre y la hora. "
             "La ve quien puede abrir este registro.")
    return redirect(destino)


@login_required
def recientes(request):
    """Las últimas observaciones de los registros que la persona puede abrir."""
    tipo = request.GET.get("tipo", "")
    consulta = Observacion.objects.select_related("autor", "delegacion").order_by("-creada")
    if tipo in O.TIPOS:
        consulta = consulta.filter(tipo=tipo)
    visibles = O._visibles(request.user)
    if visibles is not None:
        consulta = consulta.filter(delegacion_id__in=visibles)

    filas, cache = [], {}
    for obs in consulta[:200]:
        clave = (obs.tipo, obs.objeto_id)
        if clave not in cache:
            obj = O.registro(obs.tipo, obs.objeto_id)
            cache[clave] = (obj if obj is not None and O.puede(request.user, obs.tipo, obj)
                            else None)
        obj = cache[clave]
        if obj is None:
            continue
        filas.append({"obs": obs, "url": O.url_de(obs.tipo, obj) + "#observaciones"})
        if len(filas) >= 60:
            break

    return render(request, "comun/observaciones.html", {
        "menu": "observaciones",
        "filas": filas,
        "tipos": Observacion.Tipo.choices,
        "tipo": tipo,
    })

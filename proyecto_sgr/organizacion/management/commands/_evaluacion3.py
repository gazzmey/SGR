"""
Datos ficticios de la Evaluación 3, que ``cargar_datos_demo`` suma a los de
siempre.

Por cada una de las 17 entidades deja al menos dos registros válidos y uno
inactivo (o anulado), con sus relaciones; un registro **desechable** para
probar crear, editar y eliminar sin tocar nada importante; y casos de
**relación protegida**:

* el territorio «Unidad vecinal 1 · El Mirador» tiene vecinos, una junta y un
  hito activos: no se desactiva;
* la junta «Junta de Vecinos El Mirador» tiene participantes vigentes: no se
  desactiva;
* el vecino que preside esa junta no se desactiva sin terminar su
  participación;
* el hito de limpieza tiene actividades asociadas: no se desactiva.

Todos los RUT nuevos están entre 30.000.000 y 30.200.000, un tramo que no
corresponde a ninguna persona: son números con dígito verificador válido,
inventados. Los correos usan el dominio reservado ``ejemplo.cl``.

Se puede ejecutar varias veces: cada registro se busca por su código o su
RUT antes de crearse.
"""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.utils import timezone

from comun.rut import digito_verificador


def rut_ficticio(numero):
    cuerpo = 30_000_000 + numero
    return f"{cuerpo}-{digito_verificador(cuerpo)}"


def rut_de_usuario(codigo):
    """USR-07 → 30.000.007-x. Ficticio y estable."""
    return rut_ficticio(int(codigo.split("-")[1]))


def repartir(nombre):
    partes = (nombre or "").split()
    if len(partes) >= 4:
        return " ".join(partes[:-2]), " ".join(partes[-2:])
    if len(partes) >= 2:
        return " ".join(partes[:-1]), partes[-1]
    return nombre or "", ""


# --- Territorios -----------------------------------------------------------
# codigo, delegación, nombre, descripción, activo
TERRITORIOS = [
    ("TER-01", "DEL-01", "Unidad vecinal 1 · El Mirador",
     "Población El Mirador y las calles que bajan hacia la avenida principal.", True),
    ("TER-02", "DEL-01", "Unidad vecinal 2 · Los Aromos",
     "Villa Los Aromos y el pasaje del canal.", True),
    ("TER-03", "DEL-01", "Unidad vecinal 3 · San Juan",
     "Sector San Juan, desde la plaza hasta el estero.", True),
    ("TER-04", "DEL-02", "Unidad vecinal 4 · Villa Esperanza",
     "Villa Esperanza y los blocks de la calle Los Aromos.", True),
    ("TER-05", "DEL-02", "Unidad vecinal 5 · El Milagro Alto",
     "Parte alta del cerro, con acceso por la calle Los Pinos.", True),
    ("TER-06", "DEL-01", "Sector antiguo de la feria",
     "Se fusionó con la Unidad vecinal 2 y dejó de usarse.", False),
    ("TER-07", "DEL-02", "Territorio de prueba (desechable)",
     "Registro para probar editar y desactivar. No tiene nada asociado.", True),
]

#: Clave de la tabla de arriba → territorio en la base. En una base que ya
#: migró, los sectores de texto libre se convirtieron en territorios con
#: otros códigos: aquí se buscan por delegación y nombre, nunca se pisan.
_TERR = {}


def territorio_por_nombre(nombre):
    if not nombre:
        return None
    for territorio in _TERR.values():
        if territorio.nombre == nombre:
            return territorio
    from organizacion.models import Territorio

    return Territorio.objects.filter(nombre=nombre).first()


def territorios(cmd):
    from comun.utilidades import proximo_codigo
    from organizacion.models import Delegacion, Territorio

    _TERR.clear()
    delegaciones = {d.codigo: d for d in Delegacion.objects.all()}
    for clave, deleg, nombre, descripcion, activo in TERRITORIOS:
        delegacion = delegaciones[deleg]
        registro = Territorio.objects.filter(delegacion=delegacion, nombre=nombre).first()
        nuevo = registro is None
        if nuevo:
            codigo = clave if not Territorio.objects.filter(codigo=clave).exists() \
                else proximo_codigo(Territorio, "TER")
            registro = Territorio(codigo=codigo, nombre=nombre, delegacion=delegacion)
        registro.descripcion = descripcion
        registro.activo = activo
        registro.desactivada = None if activo else date(2026, 6, 30)
        registro.save()
        _TERR[clave] = registro
        cmd._informar("Territorio", registro, nuevo)


# --- Vecinos ---------------------------------------------------------------
DIRECCIONES = {
    "15834276-6": "Pasaje Los Copihues 145, El Mirador",
    "9876543-3": "Calle San Juan 802",
    "18245901-1": "Villa Los Aromos, block 3, depto. 12",
    "12456789-0": "Calle Los Pinos 77, El Milagro Alto",
    "20114558-9": "Calle Las Rosas 410, Villa Esperanza",
}
CORREOS = {
    "15834276-6": "rosa.vega@ejemplo.cl",
    "18245901-1": "fabiola.araya@ejemplo.cl",
}

# número del RUT ficticio, nombres, apellidos, teléfono, dirección, territorio, activo
VECINOS = [
    (101, "Luis Alberto", "Rojas Pérez", "9 4411 2233", "Pasaje Los Copihues 160",
     "TER-01", True),
    (102, "Carmen Gloria", "Díaz Tapia", "9 4411 5566", "Calle El Mirador 22",
     "TER-01", True),
    (103, "Patricio", "Morales Leiva", "", "Calle El Mirador 48", "TER-01", True),
    (104, "Elena", "Pizarro Rivera", "9 6677 8899", "Calle San Juan 915", "TER-03", True),
    (105, "Hernán", "Guzmán Soto", "9 2233 4455", "Villa Esperanza, casa 31", "TER-04", True),
    (106, "Marta", "Cisternas Olivares", "", "Villa Los Aromos, block 1, depto. 4",
     "TER-02", False),
    (107, "Vecino de prueba", "Desechable", "", "Dirección de prueba 1", "TER-05", True),
]


def _vecinos():
    from atencion.models import Solicitante

    terr = _TERR
    salida = {}
    for numero, nombres, apellidos, telefono, direccion, ter, activo in VECINOS:
        rut = rut_ficticio(numero)
        registro, _ = Solicitante.objects.update_or_create(
            rut=rut,
            defaults={"nombres": nombres, "apellidos": apellidos, "telefono": telefono,
                      "direccion": direccion, "territorio": terr[ter], "activo": activo,
                      "desactivada": None if activo else date(2026, 8, 31)},
        )
        salida[numero] = registro
    return salida


# --- Juntas y participaciones ---------------------------------------------
JUNTAS = [
    ("JV-01", "Junta de Vecinos El Mirador", "DEL-01", "TER-01",
     "Sede social, Pasaje Los Copihues 150", date(2008, 5, 14), True),
    ("JV-02", "Junta de Vecinos San Juan", "DEL-01", "TER-03",
     "Calle San Juan 700, sede comunitaria", date(2012, 9, 3), True),
    ("JV-03", "Junta de Vecinos Villa Esperanza", "DEL-02", "TER-04",
     "Multicancha de Villa Esperanza", date(2015, 3, 21), False),
    ("JV-04", "Junta de prueba (desechable)", "DEL-02", "TER-05",
     "Dirección de prueba 2", date(2020, 1, 15), True),
]

# código, vecino (RUT), junta, dirigente, cargo, incorporación, vigente
PARTICIPACIONES = [
    ("PJ-001", "15834276-6", "JV-01", True, "presidente", date(2019, 4, 6), True),
    ("PJ-002", 102, "JV-01", True, "secretario", date(2021, 4, 10), True),
    ("PJ-003", 101, "JV-01", False, "socio", date(2022, 7, 1), True),
    ("PJ-004", "9876543-3", "JV-02", False, "socio", date(2018, 11, 20), True),
    ("PJ-005", 103, "JV-01", False, "socio", date(2016, 3, 12), False),
]


def _juntas_y_participaciones(cmd, vecinos):
    from atencion.models import JuntaVecinos, ParticipacionJunta, Solicitante
    from organizacion.models import Delegacion

    deleg = {d.codigo: d for d in Delegacion.objects.all()}
    terr = _TERR
    juntas = {}
    for codigo, nombre, d, t, direccion, constitucion, activo in JUNTAS:
        registro, nuevo = JuntaVecinos.objects.update_or_create(
            codigo=codigo,
            defaults={"nombre": nombre, "delegacion": deleg[d], "territorio": terr[t],
                      "direccion": direccion, "fecha_constitucion": constitucion,
                      "activo": activo, "desactivada": None if activo else date(2025, 12, 31)},
        )
        juntas[codigo] = registro
        cmd._informar("Junta de vecinos", registro, nuevo)

    for codigo, vecino, junta, dirigente, cargo, desde, activo in PARTICIPACIONES:
        persona = (Solicitante.objects.get(rut=vecino) if isinstance(vecino, str)
                   else vecinos[vecino])
        registro, nuevo = ParticipacionJunta.objects.update_or_create(
            codigo=codigo,
            defaults={"vecino": persona, "junta": juntas[junta], "dirigente": dirigente,
                      "cargo": cargo, "fecha_incorporacion": desde, "activo": activo,
                      "desactivada": None if activo else date(2025, 3, 31)},
        )
        cmd._informar("Participación", registro, nuevo)


# --- Hitos -----------------------------------------------------------------
def _hitos(cmd, periodo):
    from gestion.models import Hito
    from organizacion.models import Delegacion

    deleg = {d.codigo: d for d in Delegacion.objects.all()}
    terr = _TERR
    usuarios = {u.email: u for u in User.objects.all()}
    hoy = timezone.localdate()
    filas = [
        ("HIT-01", "Operativo mensual de limpieza de microbasurales",
         "Retiro de residuos en los sitios eriazos de El Mirador, con la junta de vecinos.",
         "mensual", periodo.inicio, periodo.termino, "DEL-01", "TER-01",
         ["marcela.rios@ejemplo.cl", "soledad.guerrero@ejemplo.cl"], True),
        ("HIT-02", "Feria de servicios municipales",
         "Una jornada con módulos de todas las direcciones municipales en Villa Esperanza.",
         "unica", hoy + timedelta(days=12), hoy + timedelta(days=12), "DEL-02", "TER-04",
         ["rodrigo.tapia@ejemplo.cl", "hector.pizarro@ejemplo.cl"], True),
        ("HIT-03", "Campaña de invierno 2026",
         "Entrega de frazadas y reparación de techumbres. Terminó con el invierno.",
         "anual", date(2026, 6, 1), date(2026, 8, 31), "DEL-01", None,
         ["marcela.rios@ejemplo.cl"], False),
        ("HIT-04", "Hito de prueba (desechable)",
         "Registro para probar editar y desactivar. No tiene actividades.",
         "unica", hoy + timedelta(days=30), hoy + timedelta(days=31), "DEL-02", "TER-07",
         ["rodrigo.tapia@ejemplo.cl"], True),
    ]
    hitos = {}
    for codigo, nombre, desc, perio, ini, fin, d, t, resp, activo in filas:
        registro, nuevo = Hito.objects.update_or_create(
            codigo=codigo,
            defaults={"nombre": nombre, "descripcion": desc, "periodicidad": perio,
                      "fecha_inicio": ini, "fecha_termino": fin, "delegacion": deleg[d],
                      "territorio": terr[t] if t else None, "activo": activo,
                      "desactivada": None if activo else date(2026, 9, 1)},
        )
        registro.responsables.set([usuarios[c] for c in resp if c in usuarios])
        hitos[codigo] = registro
        cmd._informar("Hito", registro, nuevo)
    return hitos


# --- Trimestres, cargos y asignaciones ------------------------------------
def _trimestre(fecha):
    return fecha.year, (fecha.month - 1) // 3 + 1


def _limites(anio, numero):
    inicio = date(anio, 3 * (numero - 1) + 1, 1)
    fin_mes = 3 * numero
    termino = (date(anio + 1, 1, 1) if fin_mes == 12 else date(anio, fin_mes + 1, 1)) - timedelta(days=1)
    return inicio, termino


def _siguiente(anio, numero):
    return (anio + 1, 1) if numero == 4 else (anio, numero + 1)


def _libre(Periodo, codigo, anio, numero, inicio, termino):
    """
    True si se puede crear ese trimestre de demostración sin chocar con uno
    que ya exista: ni el mismo año y número, ni fechas que se crucen con un
    trimestre activo que no esté cerrado. En una base con trimestres reales,
    la demostración no inventa uno encima.
    """
    otros = Periodo.objects.exclude(codigo=codigo)
    if otros.filter(anio=anio, numero=numero).exists():
        return False
    return not (otros.filter(activo=True, inicio__lte=termino, termino__gte=inicio)
                .exclude(estado=Periodo.Estado.CERRADO).exists())


def _trimestres(cmd, periodo):
    from gestion.models import Periodo

    actual = (periodo.anio, periodo.numero)
    q = _trimestre(periodo.termino + timedelta(days=1))
    if q == actual:
        q = _siguiente(*q)
    ini, fin = _limites(*q)
    ini = max(ini, periodo.termino + timedelta(days=1))
    if _libre(Periodo, "PER-D02", q[0], q[1], ini, fin):
        registro, nuevo = Periodo.objects.update_or_create(
            codigo="PER-D02",
            defaults={"nombre": f"Trimestre {q[1]} de {q[0]} (en preparación)", "anio": q[0],
                      "numero": q[1], "inicio": ini, "termino": fin,
                      "estado": Periodo.Estado.BORRADOR,
                      "observacion": "El trimestre siguiente, todavía sin abrir."},
        )
        cmd._informar("Trimestre", registro, nuevo)
    if _libre(Periodo, "PER-D00", 2025, 3, date(2025, 7, 1), date(2025, 9, 30)):
        registro, nuevo = Periodo.objects.update_or_create(
            codigo="PER-D00",
            defaults={"nombre": "Trimestre 3 de 2025 (creado por error)", "anio": 2025, "numero": 3,
                      "inicio": date(2025, 7, 1), "termino": date(2025, 9, 30),
                      "estado": Periodo.Estado.BORRADOR, "activo": False,
                      "desactivada": date(2025, 7, 15),
                      "observacion": "Se creó cuando el sistema todavía no se usaba y se desactivó."},
        )
        cmd._informar("Trimestre", registro, nuevo)


def _cargos_y_asignaciones(cmd, periodo):
    from catalogos.models import Item
    from gestion.models import Cargo, MetaPeriodo

    for codigo, nombre, desc, activo in [
        ("CAR-D07", "Apoyo administrativo temporal",
         "Cargo de un programa que terminó. Ya no tiene personas asignadas.", False),
        ("CAR-D08", "Cargo de prueba (desechable)",
         "Registro para probar editar y desactivar. No tiene personas ni metas.", True),
    ]:
        registro, nuevo = Cargo.objects.update_or_create(
            codigo=codigo,
            defaults={"nombre": nombre, "descripcion": desc, "activo": activo,
                      "desactivada": None if activo else date(2026, 3, 31)},
        )
        cmd._informar("Cargo", registro, nuevo)

    items = {i.codigo: i for i in Item.objects.all()}
    cargos = {c.codigo: c for c in Cargo.objects.all()}
    marcela = User.objects.filter(email="marcela.rios@ejemplo.cl").first()
    if marcela is not None:
        general = MetaPeriodo.objects.filter(periodo=periodo, cargo=cargos["CAR-01"],
                                             item=items["ITM-01"], funcionario__isnull=True).first()
        if general is not None:
            registro, nuevo = MetaPeriodo.objects.update_or_create(
                periodo=periodo, cargo=cargos["CAR-01"], item=items["ITM-01"], funcionario=marcela,
                defaults={"meta": general.meta, "ponderador": general.ponderador, "activo": True,
                          "observacion": "Asignación personal de ejemplo: los mismos valores "
                                         "del cargo, a nombre de Marcela Ríos."},
            )
            if nuevo:
                cmd.stdout.write(f"  Asignación personal: {registro} (creada)")
    registro, nuevo = MetaPeriodo.objects.update_or_create(
        periodo=periodo, cargo=cargos["CAR-03"], item=items["ITM-02"], funcionario=None,
        defaults={"meta": 10, "ponderador": 0, "activo": False, "desactivada": date(2026, 10, 15),
                  "observacion": "Se asignó por error y se desactivó."},
    )
    if nuevo:
        cmd.stdout.write(f"  Asignación inactiva: {registro} (creada)")


# --- Actividades, gestiones sociales y evidencias -------------------------
def _registros(cmd, periodo, hitos, vecinos):
    from atencion.models import Atencion, CasoSocial, Solicitante
    from catalogos.models import SubAtencion
    from comun.utilidades import proximo_codigo
    from gestion.modelos_actividad import Actividad, Evidencia
    from gestion.models import MetaPeriodo
    from organizacion.models import Delegacion

    usuarios = {u.email: u for u in User.objects.all()}
    marcela = usuarios.get("marcela.rios@ejemplo.cl")
    jorge = usuarios.get("jorge.salinas@ejemplo.cl")
    pablo = usuarios.get("pablo.fuentes@ejemplo.cl")
    del1 = Delegacion.objects.get(codigo="DEL-01")
    ter1 = _TERR["TER-01"]
    rosa = Solicitante.objects.filter(rut="15834276-6").first()
    hoy = timezone.localdate()

    # Antecedentes completos en algunas actividades de Marcela.
    if marcela is not None:
        suyas = list(Actividad.objects.filter(funcionario=marcela, periodo=periodo)
                     .order_by("codigo")[:6])
        for indice, act in enumerate(suyas):
            Actividad.objects.filter(pk=act.pk).update(
                tipo="terreno" if indice % 2 == 0 else "reunion",
                origen="comunidad" if indice % 3 == 0 else "planificada",
                territorio=ter1, hito=hitos["HIT-01"] if indice < 3 else None,
                solicitante=rosa if indice % 3 == 0 else None,
                fecha_compromiso=act.fecha + timedelta(days=7),
                apoyo="Camioneta municipal y cuadrilla de aseo" if indice < 3 else "",
                resultado="Se cumplió lo acordado con la junta de vecinos.",
            )

    # Dos actividades sin evidencia (para adjuntarles una) y una anulada.
    def registrar(codigo, persona, fecha, accion, estado, motivo=""):
        perfil = getattr(persona, "perfil", None)
        meta = (MetaPeriodo.objects.filter(periodo=periodo, cargo=perfil.cargo_asignado,
                                           funcionario__isnull=True, activo=True)
                .order_by("item__codigo").first() if perfil and perfil.cargo_asignado_id else None)
        if meta is None:
            return None
        act, nuevo = Actividad.objects.update_or_create(
            codigo=codigo,
            defaults={"funcionario": persona, "delegacion": del1, "periodo": periodo,
                      "item": meta.item, "asignacion": meta, "fecha": fecha, "cantidad": 1,
                      "accion": accion, "detalle": accion + ". Registro de ejemplo de la Evaluación 3.",
                      "estado": estado, "motivo_anulacion": motivo, "territorio": ter1,
                      "tipo": "terreno", "origen": "planificada", "responsable": persona,
                      "avance": 100 if estado != "borrador" else 60},
        )
        cmd._informar("Actividad", act, nuevo)
        return act

    if marcela is not None:
        registrar("ACT-E001", marcela, hoy - timedelta(days=2),
                  "Reunión con la directiva de la junta El Mirador", "borrador")
    if jorge is not None:
        registrar("ACT-E002", jorge, hoy - timedelta(days=3),
                  "Inspección de la vereda levantada de calle El Mirador", "borrador")
        anulada = registrar("ACT-E003", jorge, hoy - timedelta(days=5),
                            "Visita duplicada por error al sitio eriazo", "anulada",
                            "Se registró dos veces la misma visita; vale la del día anterior.")
        if anulada is not None and pablo is not None:
            Evidencia.objects.update_or_create(
                codigo="EVI-E003",
                defaults={"actividad": anulada, "caso": None, "tipo": "fotografia",
                          "descripcion": "Foto del sitio eriazo (registro duplicado)",
                          "referencia": "Carpeta compartida / fotos / visita-duplicada.jpg",
                          "autor": jorge, "anulada": True,
                          "motivo_anulacion": "Se registró dos veces la misma visita."},
            )

    # Una gestión social anulada, con su propia atención.
    sub = SubAtencion.objects.filter(codigo="SAT-01").first()
    luis = vecinos.get(101)
    if sub is not None and luis is not None and marcela is not None:
        atencion = Atencion.objects.filter(solicitante=luis, subatencion=sub, delegacion=del1).first()
        if atencion is None:
            atencion = Atencion.objects.create(
                solicitante=luis, subatencion=sub, delegacion=del1, funcionario=marcela,
                detalle="Solicita caja de mercadería. Se abrió el caso y después se supo "
                        "que ya la recibía por otro programa.",
                documento="Informe social 2026-0599")
        caso, nuevo = CasoSocial.objects.update_or_create(
            codigo="CSO-D04",
            defaults={"atencion": atencion, "responsable": marcela,
                      "ingreso": hoy - timedelta(days=10), "fecha_atencion": hoy - timedelta(days=10),
                      "requiere_visita": False, "lleva_beneficio": True,
                      "estado": CasoSocial.Estado.ANULADO,
                      "motivo_anulacion": "La persona ya recibía la ayuda por otro programa: "
                                          "el caso se abrió por duplicado.",
                      "derivacion": "Programa alimentario regional"},
        )
        cmd._informar("Gestión social", caso, nuevo)

    # Evidencias de gestiones sociales: una aprobada y una pendiente.
    for codigo, caso_codigo, tipo, desc, ref, aprobada in [
        ("EVI-E001", "CSO-D01", "informe", "Informe social de la visita domiciliaria",
         "Informe social 2026-0931", True),
        ("EVI-E002", "CSO-D02", "acta", "Acta de la coordinación telefónica",
         "Libro de actas de la delegación, folio 88", False),
    ]:
        caso = CasoSocial.objects.filter(codigo=caso_codigo).select_related("atencion").first()
        if caso is None:
            continue
        verificador = pablo if aprobada and pablo and pablo.pk != caso.responsable_id else None
        Evidencia.objects.update_or_create(
            codigo=codigo,
            defaults={"actividad": None, "caso": caso, "tipo": tipo, "descripcion": desc,
                      "referencia": ref, "autor": caso.responsable,
                      "decision": "aprobada" if verificador else "pendiente",
                      "verificador": verificador,
                      "decidida": timezone.now() if verificador else None},
        )


def _delegados():
    from organizacion.models import Delegacion

    for codigo, correo in (("DEL-01", "soledad.guerrero@ejemplo.cl"),
                           ("DEL-02", "rodrigo.tapia@ejemplo.cl")):
        persona = User.objects.filter(email=correo).first()
        if persona is not None:
            Delegacion.objects.filter(codigo=codigo).update(delegado=persona)


def _catalogo_desechable(cmd):
    from catalogos.models import SubAtencion, TipoAtencion

    tipo, nuevo = TipoAtencion.objects.update_or_create(
        codigo="TAT-D09",
        defaults={"nombre": "Tipo de prueba (desechable)", "area": "Transversal",
                  "descripcion": "Registro para probar editar y desactivar. Tiene un subtipo."},
    )
    cmd._informar("Tipo de atención", tipo, nuevo)
    sub, nuevo = SubAtencion.objects.update_or_create(
        codigo="SAT-D25",
        defaults={"nombre": "Subtipo de prueba (desechable)", "tipo_atencion": tipo,
                  "descripcion": "Registro para probar editar y desactivar.", "documento": False},
    )
    cmd._informar("Subtipo de atención", sub, nuevo)


def cargar(cmd):
    """Lo que la Evaluación 3 suma a la demostración, después de lo de siempre."""
    from gestion.models import Periodo

    periodo = Periodo.objects.get(codigo="PER-01")
    if not _TERR:
        territorios(cmd)
    _delegados()
    vecinos = _vecinos()
    _juntas_y_participaciones(cmd, vecinos)
    hitos = _hitos(cmd, periodo)
    _trimestres(cmd, periodo)
    _cargos_y_asignaciones(cmd, periodo)
    _catalogo_desechable(cmd)
    _registros(cmd, periodo, hitos, vecinos)

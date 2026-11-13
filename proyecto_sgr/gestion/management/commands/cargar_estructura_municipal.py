"""
Carga la estructura real con que se miden las delegaciones de La Serena.

Viene de dos documentos de la Coordinación de Delegaciones:

· el **Descriptor de funciones para los cargos de las Delegaciones
  Municipales** (versión 2026), del que salen los cargos y sus funciones;
· la **Matriz SGR** del trimestre, una planilla con una hoja por cargo, de
  la que salen los ítems, sus ponderadores y sus metas trimestrales.

**No carga ningún dato personal.** La matriz trae nombres, RUT, teléfonos y
direcciones de vecinos y de funcionarios; de ella solo se toma la estructura
—qué se mide, cuánto pesa y cuánto se pide—, que es lo mismo para todas las
personas de un cargo.

    python manage.py cargar_estructura_municipal
    python manage.py cargar_estructura_municipal --periodo PER-02
    python manage.py cargar_estructura_municipal --periodo PER-02 --regla

Sin opciones crea o actualiza los cargos, los ítems del catálogo y los tipos
y subatenciones sociales de la hoja LISTA. Con ``--periodo`` además crea las
metas de cada cargo en ese período, y con ``--regla`` una regla de cálculo
propia del período con el tope de 120 % acordado (la matriz decía 150 %). Se puede
ejecutar varias veces: cada registro se busca por su nombre antes de crearse.

Lo que la matriz no deja claro y se resolvió así
------------------------------------------------
· **Las hojas de un mismo cargo no son idénticas.** «G SOC2» pondera 25 / 20
  / 20 donde «G SOC 1» pondera 20 / 20 / 25. El sistema mide por cargo, no
  por persona, así que se usa la primera hoja de cada cargo.
· **«PLAN y CON» suma 85 %**, no 100 %: la propia planilla muestra 0,85 en su
  total. Se carga tal cual y el sistema avisa que el cargo está incompleto.
· **El Delegado y el Gestor de Compras y Proyectos** están en el descriptor
  pero no tienen hoja en la matriz: se crean con sus funciones y sin metas.
· **El Gestor de Seguridad** tiene hoja (GES SEG) pero no está en el
  descriptor: se crea con sus ítems y sin funciones.
· **Emergencia** no tiene meta fija en la matriz: se carga como ítem que se
  cumple con una sola actividad. **Soluciones de ingresos al tubo** se carga
  como ítem medido por la agenda, con meta de 80 %.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalogos.models import Area, Item, SubAtencion, TipoAtencion
from comun.utilidades import proximo_codigo
from gestion.models import Cargo, MetaPeriodo, Periodo
from gestion.modelos_versiones import VersionParametro
from gestion.reglas import PROPUESTA_DEL_PLAN, ReglaCalculo
from gestion.versiones import versionar

COMANDO = VersionParametro.Origen.COMANDO

ORIGEN = "Matriz SGR de las delegaciones, trimestre 2026"

# --- ítems -----------------------------------------------------------------
# código, nombre, área, cómo se mide, unidad, meta sugerida, qué cuenta.
A = Item.Medicion.ACTIVIDADES
G = Item.Medicion.AGENDA
P = Item.Medicion.PRESENCIA
CANT = Item.Unidad.CANTIDAD
PORC = Item.Unidad.PORCENTAJE

ITEMS = [
    ("MZ-01", "Atención de usuarios telefónica y presencial", Area.TRANSVERSAL, A, CANT, 60,
     "Cada atención a un vecino o vecina, por teléfono o en la oficina, registrada con lo que se le resolvió."),
    ("MZ-02", "Llamadas preventivas a usuarios", Area.TRANSVERSAL, A, CANT, 90,
     "Llamadas de seguimiento a personas ya atendidas, a partir del registro de atenciones."),
    ("MZ-03", "Informe de inventario", Area.TRANSVERSAL, A, CANT, 1,
     "El inventario trimestral de la delegación, entregado a la coordinación."),
    ("MZ-04", "Informe a Comunicaciones", Area.TRANSVERSAL, A, CANT, 12,
     "El envío semanal de la agenda y las actividades de la delegación a Comunicaciones."),
    ("MZ-05", "Emergencia", Area.TERRITORIAL, P, CANT, 1,
     "Atención de una emergencia en el territorio. Sin meta fija: se cumple con al menos una registrada."),
    ("MZ-06", "Soluciones de ingresos al tubo", Area.TRANSVERSAL, G, PORC, 80,
     "Porcentaje de los compromisos de la agenda a cargo de la persona que quedaron realizados."),
    ("MZ-07", "Informes del personal de cuadrillas", Area.TERRITORIAL, A, CANT, 3,
     "Informe mensual del personal de las cuadrillas, para el pago de remuneraciones."),
    ("MZ-08", "Informe semanal de trabajo", Area.TERRITORIAL, A, CANT, 12,
     "Informe semanal de lo ejecutado por las cuadrillas de empleabilidad y emergencia."),
    ("MZ-09", "Operativos de la delegación", Area.TERRITORIAL, A, CANT, 24,
     "Operativos de limpieza, desmalezado o mejoramiento organizados por la delegación."),
    ("MZ-10", "Operativos con DISERCO", Area.TERRITORIAL, A, CANT, 12,
     "Operativos coordinados con la dirección de servicios a la comunidad."),
    ("MZ-11", "Talleres de educación ambiental", Area.TERRITORIAL, A, CANT, 12,
     "Talleres de reciclaje, compostaje, aseo y ornato con la comunidad."),
    ("MZ-12", "Evaluaciones técnicas en terreno", Area.TERRITORIAL, A, CANT, 24,
     "Salidas a terreno para analizar una obra de mejoramiento: caminos, desmalezado, alumbrado."),
    ("MZ-13", "Atención de requerimientos de usuarios", Area.TERRITORIAL, A, CANT, 24,
     "Requerimientos de servicios comunitarios recibidos y canalizados a la unidad que corresponde."),
    ("MZ-14", "Visitas y reuniones con organizaciones", Area.TERRITORIAL, A, CANT, 24,
     "Visitas o reuniones con juntas de vecinos y organizaciones, con levantamiento de necesidades."),
    ("MZ-15", "Conformación de organizaciones", Area.TERRITORIAL, A, CANT, 1,
     "Organizaciones comunitarias nuevas asesoradas hasta su constitución, según las leyes 19.418 y 20.500."),
    ("MZ-16", "Gestión de talleres y actividades", Area.TERRITORIAL, A, CANT, 6,
     "Talleres y actividades con organizaciones, para mantener la motivación y la educación en temas municipales."),
    ("MZ-17", "Atención social presencial", Area.SOCIAL, A, CANT, 90,
     "Recepción y evaluación de un caso social en la oficina."),
    ("MZ-18", "Visita social a terreno", Area.SOCIAL, A, CANT, 12,
     "Visita domiciliaria o en terreno para evaluar un caso social."),
    ("MZ-19", "Entrega de informe social", Area.SOCIAL, A, CANT, 40,
     "Informe social entregado: aporte económico, aporte material o para una institución."),
    ("MZ-20", "Entrega de beneficio", Area.SOCIAL, A, CANT, 8,
     "Entrega del beneficio que resolvió el caso social, con su recepción conforme."),
    ("MZ-21", "Reunión semanal con el equipo", Area.TRANSVERSAL, A, CANT, 12,
     "La reunión semanal de coordinación del equipo de la delegación, con su registro."),
    ("MZ-22", "Solución de problemas a usuarios particulares", Area.TRANSVERSAL, A, CANT, 8,
     "Casos particulares derivados por la jefatura o por gabinete y resueltos por gestión y planificación."),
    ("MZ-23", "Formación de comités de seguridad", Area.TERRITORIAL, A, CANT, 36,
     "Reuniones de formación o seguimiento de comités vecinales de seguridad."),
    ("MZ-24", "Levantamiento de incivilidades", Area.TERRITORIAL, A, CANT, 40,
     "Registro de incivilidades detectadas en el territorio y su derivación."),
    ("MZ-25", "Gestión de mediación", Area.TERRITORIAL, A, CANT, 50,
     "Mediaciones vecinales gestionadas, con o sin acuerdo."),
    ("MZ-26", "Recuperación de espacios públicos", Area.TERRITORIAL, A, CANT, 50,
     "Acciones de recuperación de plazas, sitios y espacios públicos con la comunidad."),
    ("MZ-27", "Infracciones varias", Area.INSPECCION, A, CANT, 45,
     "Infracciones constatadas y derivadas a la unidad que fiscaliza."),
    ("MZ-28", "Salidas a terreno de seguridad", Area.TERRITORIAL, A, CANT, 45,
     "Recorridos y salidas a terreno del equipo de seguridad."),
]

# --- cargos ----------------------------------------------------------------
# nombre, descripción, funciones (una por línea) y metas: (ítem, meta,
# ponderador). Las funciones son las del descriptor 2026, transcritas.
CARGOS = [
    ("Delegado municipal",
     "Representante directo de la alcaldía en su territorio. Es el puente entre "
     "el municipio y los sectores más alejados o poblados: acerca la atención "
     "social, asesora a los dirigentes y gestiona soluciones locales.",
     [
         "Informar a la autoridad comunal sobre situaciones que pudieran ocurrir en su territorio, para adoptar las medidas preventivas correspondientes.",
         "Ser representante de la máxima autoridad comunal en su territorio, empoderándose de su cargo para enfrentar y solucionar las necesidades permanentes de los usuarios.",
         "Responder por el buen funcionamiento del territorio, desde la parte interna administrativa hasta el cumplimiento de las gestiones encomendadas a la delegación.",
         "Visitar periódicamente juntas de vecinos y organizaciones comunitarias, para estar presente, acompañar y apoyar.",
         "Proponer y dar soluciones a las necesidades y problemas de los usuarios del sector, para potenciar y mejorar la gestión de los servicios municipales.",
         "Poner en práctica y supervisar el cumplimiento de planes y políticas de desarrollo que beneficien a la comunidad, según lo dispuesto por la máxima autoridad comunal.",
         "Mantener buena relación y comunicación con las direcciones y departamentos del municipio y con las organizaciones públicas y sociales, para apoyar a su equipo en las tareas encomendadas.",
         "Difundir los programas y actividades implementados por la municipalidad.",
         "Delegar en su equipo los trabajos solicitados por la comunidad, orientando y guiando el buen desempeño de las acciones.",
         "Generar mesas de trabajo con estamentos públicos y privados, siendo el puente para los usuarios que necesitan atención.",
         "Ejecutar otras funciones que la ley señale o que le encomiende el alcalde o el Administrador Municipal en el ámbito de sus competencias.",
     ],
     []),
    ("Gestor social",
     "Trabajadora o trabajador social de la delegación: desarrolla acciones "
     "comunitarias y atiende casos para promover el bienestar de la comunidad, "
     "especialmente de quienes están en situación de vulnerabilidad.",
     [
         "Atención de casos: recepción y evaluación de casos.",
         "Atención de casos: diagnóstico y planificación.",
         "Atención de casos: intervención y seguimiento.",
         "Atención de casos: derivación y articulación.",
         "Atención de casos: visitas en terreno.",
         "Acciones comunitarias: diagnóstico comunitario.",
         "Acciones comunitarias: planificación y ejecución de programas.",
         "Acciones comunitarias: organización y participación comunitaria.",
         "Acciones comunitarias: articulación con organizaciones de apoyo social.",
         "Coordinación con otros servicios y programas municipales, para asegurar la atención integral de los ciudadanos.",
         "Gestión de recursos para la atención de casos y la ejecución de programas comunitarios.",
         "Elaboración de informes y estadísticas sobre la atención de casos y las acciones comunitarias.",
         "Participación en reuniones y comités.",
         "Capacitación y actualización.",
         "Apoyo a la gestión municipal.",
     ],
     [("MZ-17", 90, 20), ("MZ-18", 12, 20), ("MZ-19", 40, 25), ("MZ-20", 8, 20),
      ("MZ-05", 1, 5), ("MZ-06", 80, 10)]),
    ("Apoyo administrativo",
     "Asiste en la gestión documental y la atención ciudadana, lleva la agenda "
     "y la logística de la delegación, tramita expedientes y administra la "
     "base de datos.",
     [
         "Llevar la agenda del delegado, para coordinar los eventos y reuniones en que debe participar, ordenando y centralizando la información.",
         "Coordinar el transporte de la delegación.",
         "Ser encargado o encargada de los auxiliares, la mantención y el aseo.",
         "Atender al público y derivar a las áreas correspondientes dentro de la delegación.",
         "Generar el registro de atenciones en la planilla SGR, para después llamar preventivamente al usuario.",
         "Generar el inventario trimestral de la delegación.",
         "Entregar materiales a los funcionarios.",
         "Retroalimentar la gestión del delegado con las solicitudes ingresadas por la comunidad: correos al alias, cartas, oficina y oficina de partes.",
         "Elaborar los informes mensuales del personal administrativo (excluida empleabilidad): permisos, solicitudes, carpetas para pago y documentos para transparencia.",
         "Enviar la agenda a Comunicaciones.",
         "Atender temas varios de procesos administrativos para cumplir los objetivos de la delegación.",
     ],
     [("MZ-01", 240, 20), ("MZ-02", 90, 30), ("MZ-03", 1, 25), ("MZ-04", 12, 20),
      ("MZ-05", 1, 5)]),
    ("Organizaciones comunitarias",
     "Responsable del registro de organizaciones y de facilitar la formación, "
     "legalización y asesoría de juntas de vecinos y agrupaciones funcionales "
     "bajo las leyes 19.418 y 20.500.",
     [
         "Potenciar integralmente el desarrollo de los territorios en beneficio de la comunidad.",
         "Crear organizaciones nuevas y mantener la vigencia, o el cierre, de las organizaciones comunitarias inactivas.",
         "Asesorar y capacitar en temáticas y procedimientos de las organizaciones comunitarias.",
         "Levantar necesidades en cada territorio, con visitas junto a los dirigentes de cada organización.",
         "Generar las convocatorias a las actividades municipales que se realicen.",
         "Articular a las organizaciones comunitarias con las áreas municipales, para cumplir los requerimientos y necesidades de los usuarios.",
         "Generar actividades y talleres con las organizaciones, manteniendo la motivación y aumentando la educación en temas municipales.",
         "Atender temas varios de procesos administrativos para cumplir los objetivos de la delegación.",
     ],
     [("MZ-01", 60, 15), ("MZ-14", 24, 15), ("MZ-15", 1, 25), ("MZ-16", 6, 15),
      ("MZ-05", 1, 5), ("MZ-06", 80, 25)]),
    ("Gestor de compras y proyectos",
     "Tramita los requerimientos de adquisición de bienes y servicios de su "
     "dirección ante las unidades revisora, gestionadora y de compra. Se "
     "designa por decreto alcaldicio, con titular y suplente.",
     [
         "Recopilar y confeccionar la planificación operativa anual de su dirección, considerando los requerimientos de todas sus unidades.",
         "Hacer control de gestión del cumplimiento del plan anual de compras de su dirección, evaluando permanentemente sus necesidades con el director respectivo.",
         "Revisar pliegos de condiciones, marcos de referencia y especificaciones técnicas, dando su visto bueno antes de remitirlos a la unidad revisora.",
         "Elaborar con la debida anticipación las solicitudes u oficios internos de contratación de bienes y servicios de su dirección.",
         "Incorporar en las solicitudes la propuesta de comisión evaluadora o evaluador, y del inspector técnico de contrato titular y subrogante.",
     ],
     []),
    ("Gestión y planificación",
     "Alinea los objetivos estratégicos de la delegación con su operación "
     "diaria: diseña planes de acción, monitorea el rendimiento con "
     "indicadores y optimiza la toma de decisiones.",
     [
         "Derivar y apoyar a cada área en la realización y entrega de los informes solicitados por la jefatura.",
         "Apoyar con registros el levantamiento y la actualización del diagnóstico de necesidades de la comunidad, y los listados de información estratégica.",
         "Mantener el buen funcionamiento de los procesos de la delegación, coordinando al personal y derivando las tareas del día a día.",
         "Informar al delegado sobre el trabajo de la matriz SGR, con las fortalezas y debilidades de cada colaborador, anticipándose a los resultados.",
         "Informar oportunamente al delegado sobre materias de interés del sector.",
         "Coordinarse con los departamentos internos y con el equipo de coordinación de las delegaciones cuando la jefatura lo requiera.",
         "Tomar acciones rápidas de solución a problemas derivados desde gabinete.",
         "Representar a la delegación cuando el delegado lo solicite.",
         "Coordinarse con los departamentos municipales para la consecución de los objetivos.",
         "Responder por el buen llenado de la matriz SGR.",
         "Gestionar la reunión semanal.",
         "Atender temas varios de procesos administrativos para cumplir los objetivos de la delegación.",
     ],
     [("MZ-21", 12, 15), ("MZ-22", 8, 30), ("MZ-05", 1, 5), ("MZ-06", 80, 35)]),
    ("Coordinador de servicios comunitarios",
     "Planifica, coordina y ejecuta iniciativas de aseo, ornato y medio "
     "ambiente en beneficio de la comunidad.",
     [
         "Ser enlace permanente entre la municipalidad y las juntas de vecinos, organizaciones funcionales, clubes deportivos y agrupaciones ambientales para operativos de limpieza y reparaciones de bienes nacionales de uso público.",
         "Atender al usuario en la oficina y en terreno cuando se requiere un análisis técnico para una obra de mejoramiento (caminos, desmalezado, etc.).",
         "Coordinar la ejecución y el seguimiento de operativos de limpieza y desmalezado, mejoramiento de barrios y recuperación de espacios.",
         "Liderar y coordinar acciones de educación ambiental (talleres de reciclaje, compostaje, aseo y ornato), operativos de limpieza y programas de reciclaje.",
         "Responder por el buen funcionamiento operativo y administrativo de las cuadrillas del programa de empleabilidad y de la cuadrilla de emergencia.",
         "Coordinar acciones con las direcciones municipales (Aseo y Ornato, Operaciones, Maquinarias) para garantizar servicios eficientes.",
         "Recibir, canalizar y hacer seguimiento de las denuncias ciudadanas por uso indebido de los espacios públicos.",
         "Elaborar informes de gestión periódicos del programa de empleabilidad y de las cuadrillas.",
         "Atender temas varios de procesos administrativos en el área de servicios a la comunidad.",
     ],
     [("MZ-07", 3, 10), ("MZ-08", 12, 10), ("MZ-09", 24, 15), ("MZ-10", 12, 10),
      ("MZ-11", 12, 10), ("MZ-12", 24, 10), ("MZ-13", 24, 15), ("MZ-05", 1, 5),
      ("MZ-06", 80, 15)]),
    ("Gestor de seguridad",
     "Cargo que la matriz SGR mide en la hoja GES SEG. El descriptor de "
     "funciones 2026 no lo detalla, así que se carga sin funciones.",
     [],
     [("MZ-23", 36, 20), ("MZ-24", 40, 20), ("MZ-25", 50, 10), ("MZ-26", 50, 10),
      ("MZ-27", 45, 15), ("MZ-28", 45, 10), ("MZ-06", 80, 15)]),
]

# --- tipos y subatenciones sociales (hoja LISTA) ----------------------------
# tipo, descripción del tipo, [(subatención, descripción, exige respaldo)].
TIPOS_SOCIALES = [
    ("Informes sociales",
     "Atenciones que terminan en un informe social, que es el respaldo del aporte.",
     [("Informe de aporte económico", "Informe social para un aporte en dinero.", True),
      ("Informe de aporte material", "Informe social para un aporte en materiales.", True),
      ("Informe para institución", "Informe social solicitado por una institución.", True)]),
    ("Gestión de subsidios",
     "Postulación o trámite de un subsidio o beneficio del Estado.",
     [("Trámite en el IPS", "Gestión ante el Instituto de Previsión Social.", False),
      ("Pensión Garantizada Universal (PGU)", "Orientación o trámite de la PGU.", False),
      ("Subsidio Único Familiar (SUF)", "Orientación o postulación al SUF.", False),
      ("Subsidio al Agua Potable (SAP)", "Postulación al subsidio de agua potable.", False)]),
    ("Otras gestiones sociales",
     "Gestiones sociales que no terminan en informe ni en subsidio.",
     [("Exención de pago de aseo domiciliario", "Postulación a la exención del derecho de aseo.", False),
      ("Orientación social", "Orientación a la persona sobre sus alternativas.", False)]),
    ("Derivaciones",
     "Casos que se derivan a otra unidad o institución.",
     [("Derivación a otra unidad", "Derivación del caso a otra unidad municipal o institución.", False)]),
]


class Command(BaseCommand):
    help = "Carga los cargos del descriptor y la estructura de la matriz SGR, sin datos personales."

    def add_arguments(self, parser):
        parser.add_argument(
            "--periodo",
            help="Código del período donde crear las metas de cada cargo (por ejemplo PER-02).",
        )
        parser.add_argument(
            "--regla", action="store_true",
            help="Crea o actualiza una regla de cálculo propia del período, con el tope acordado de 120 %%.",
        )
        parser.add_argument(
            "--sin-catalogo-social", action="store_true",
            help="No cargar los tipos y subatenciones sociales de la hoja LISTA.",
        )

    @transaction.atomic
    def handle(self, *args, **opciones):
        periodo = None
        if opciones["periodo"]:
            periodo = Periodo.objects.filter(codigo=opciones["periodo"]).first()
            if periodo is None:
                raise CommandError(f"No existe el período {opciones['periodo']}.")
            if periodo.estado == Periodo.Estado.CERRADO:
                raise CommandError(
                    f"«{periodo.nombre}» está cerrado: sus metas quedaron congeladas."
                )
        elif opciones["regla"]:
            raise CommandError("--regla necesita --periodo: la regla es de un período.")

        items = self._items()
        cargos = self._cargos()
        if not opciones["sin_catalogo_social"]:
            self._catalogo_social()
        if periodo is not None:
            self._metas(periodo, cargos, items)
            if opciones["regla"]:
                self._regla(periodo)

        self.stdout.write(self.style.SUCCESS(
            "Estructura cargada: %d cargos y %d ítems de la matriz%s."
            % (len(cargos), len(items),
               f", con sus metas en «{periodo.nombre}»" if periodo else "")
        ))
        incompletos = [
            nombre for nombre, _, _, metas in CARGOS
            if metas and sum(p for _, _, p in metas) != 100
        ]
        for nombre in incompletos:
            suma = sum(p for n, _, _, metas in CARGOS if n == nombre for _, _, p in metas)
            self.stdout.write(self.style.WARNING(
                f"Ojo: en la matriz, «{nombre}» suma {suma} %, no 100 %. Se cargó tal cual."
            ))

    # ------------------------------------------------------------------

    def _items(self):
        creados = {}
        for codigo, nombre, area, medicion, unidad, meta, descripcion in ITEMS:
            item = (Item.objects.filter(nombre__iexact=nombre).first()
                    or Item.objects.filter(codigo=codigo).first())
            nuevo = item is None
            if nuevo:
                item = Item(codigo=codigo)
            item.nombre = item.nombre if not nuevo else nombre
            item.area = area
            item.medicion = medicion
            item.unidad = unidad
            item.meta = meta
            if not item.descripcion:
                item.descripcion = f"{descripcion} ({ORIGEN})."
            item.activo = True
            item.desactivada = None
            antes = None if nuevo else Item.objects.get(pk=item.pk).datos_version()
            item.full_clean()
            item.save()
            versionar(item, antes=antes, origen=COMANDO)
            creados[codigo] = item
            self._informar("Ítem", item, nuevo)
        return creados

    def _cargos(self):
        creados = {}
        for nombre, descripcion, funciones, _ in CARGOS:
            cargo = Cargo.objects.filter(nombre__iexact=nombre).first()
            nuevo = cargo is None
            if nuevo:
                cargo = Cargo(codigo=proximo_codigo(Cargo, "CAR"), nombre=nombre)
            cargo.descripcion = descripcion
            cargo.funciones = "\n".join(funciones)
            cargo.save()
            creados[nombre] = cargo
            self._informar("Cargo", cargo, nuevo)
        return creados

    def _catalogo_social(self):
        for tipo_nombre, tipo_desc, subs in TIPOS_SOCIALES:
            tipo = TipoAtencion.objects.filter(nombre__iexact=tipo_nombre).first()
            nuevo = tipo is None
            if nuevo:
                tipo = TipoAtencion.objects.create(
                    codigo=proximo_codigo(TipoAtencion, "TAT"), nombre=tipo_nombre,
                    descripcion=tipo_desc, area=Area.SOCIAL,
                )
            self._informar("Tipo de atención", tipo, nuevo)
            for sub_nombre, sub_desc, respaldo in subs:
                sub = SubAtencion.objects.filter(nombre__iexact=sub_nombre).first()
                nuevo = sub is None
                if nuevo:
                    sub = SubAtencion.objects.create(
                        tipo_atencion=tipo, codigo=proximo_codigo(SubAtencion, "SAT"),
                        nombre=sub_nombre, descripcion=sub_desc, documento=respaldo,
                    )
                self._informar("Subatención", sub, nuevo)

    def _metas(self, periodo, cargos, items):
        for nombre, _, _, metas in CARGOS:
            for codigo_item, meta, ponderador in metas:
                previa = MetaPeriodo.objects.filter(
                    periodo=periodo, cargo=cargos[nombre], item=items[codigo_item]).first()
                antes = previa.datos_version() if previa else None
                registro, nuevo = MetaPeriodo.objects.update_or_create(
                    periodo=periodo, cargo=cargos[nombre], item=items[codigo_item],
                    defaults={"meta": meta, "ponderador": ponderador, "activo": True},
                )
                versionar(registro, antes=antes, origen=COMANDO)
                if nuevo:
                    self.stdout.write(f"  Meta: {registro} ({ponderador} %) (creada)")

    def _regla(self, periodo):
        valores = dict(PROPUESTA_DEL_PLAN)
        valores.update({
            # La hoja RECLAMOS de la matriz decía «el sobrecumplimiento de
            # cada colaborador no puede ser mayor a 150 %». El equipo acordó
            # 120 %, y ese es el tope que se carga.
            "tope_aporte": 120,
            "periodo": periodo,
            "aprobada": False,
            "aprobada_por": "",
            "observacion": (
                "Valores de la matriz SGR de las delegaciones, con el tope "
                "acordado de 120 % (la matriz decía 150 %), "
                "+10 por felicitación (hasta 3), −20 por reclamo, plazos de los "
                "casos sociales de las hojas G SOC. Falta confirmar si el "
                "reclamo descuenta 20 o 30: la matriz usa los dos."
            ),
        })
        regla = ReglaCalculo.objects.filter(periodo=periodo, activo=True).first()
        nuevo = regla is None
        antes = None if nuevo else regla.datos_version()
        if nuevo:
            regla = ReglaCalculo(nombre=f"Matriz SGR · {periodo.nombre}"[:80])
        for campo, valor in valores.items():
            setattr(regla, campo, valor)
        regla.activo = True
        regla.full_clean()
        regla.save()
        versionar(regla, antes=antes, origen=COMANDO)
        self._informar("Regla de cálculo", regla, nuevo)

    def _informar(self, etiqueta, registro, nuevo):
        self.stdout.write(f"  {etiqueta}: {registro} ({'creado' if nuevo else 'actualizado'})")

"""
Plan mínimo de comprobaciones de la Evaluación 3, automatizado.

    python manage.py test pruebas

Recorre las 17 entidades con los dos perfiles de prueba —Consulta y
Gestión— y comprueba, para cada una, lo que pide la sección 10 del
enunciado: crear, listar, ver y editar funcionan; se elimina o se desactiva
según la estrategia documentada; un formulario inválido no guarda nada; las
relaciones protegidas se respetan; el acceso sin sesión lleva al login; la
consulta recibe 403 al intentar modificar; GET no modifica; los formularios
exigen CSRF; un identificador inexistente responde 404.

Usa los mismos datos de ``cargar_datos_demo``. La base de pruebas la crea
Django y la borra al terminar: en MySQL/MariaDB el usuario de la conexión
necesita permiso para crear bases de datos.
"""

import os
import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from atencion.models import CasoSocial, JuntaVecinos, ParticipacionJunta, Solicitante
from catalogos.models import Item, SubAtencion, TipoAtencion
from comun.entidades import ENTIDADES
from comun.rut import digito_verificador
from gestion.modelos_actividad import Actividad, Evidencia
from gestion.models import Cargo, Hito, MetaPeriodo, Periodo
from organizacion.models import Delegacion, PerfilUsuario, Rol, Territorio

U = get_user_model()


#: Clave de las cuentas en la base de pruebas, que Django crea y borra. Se
#: genera al correr: ninguna contraseña queda escrita en el repositorio.
if not os.environ.get("SGR_DEMO_PASSWORD"):
    os.environ["SGR_DEMO_PASSWORD"] = "Prueba-" + secrets.token_urlsafe(12)


def rut(numero):
    cuerpo = 30_190_000 + numero
    return f"{cuerpo}-{digito_verificador(cuerpo)}"


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_datos_demo", verbosity=0, stdout=open(os.devnull, "w"))

    def setUp(self):
        self.consulta = self._cliente("consulta@ejemplo.cl")
        self.gestion = self._cliente("gestion@ejemplo.cl")
        self.hoy = timezone.localdate()
        self.del1 = Delegacion.objects.get(codigo="DEL-01")
        self.ter1 = Territorio.objects.get(codigo="TER-01")
        self.marcela = U.objects.get(email="marcela.rios@ejemplo.cl")
        self.periodo = Periodo.objects.get(codigo="PER-01")

    @staticmethod
    def _cliente(correo):
        c = Client()
        c.force_login(U.objects.get(email=correo))
        return c

    # --- datos válidos para crear cada entidad -----------------------------

    def datos(self, clave):
        hoy = self.hoy
        sat01 = SubAtencion.objects.get(codigo="SAT-01")
        meta_cargo = MetaPeriodo.objects.filter(
            periodo=self.periodo, cargo__codigo="CAR-01", funcionario__isnull=True,
            item__codigo="ITM-02").first()
        return {
            "delegacion": {"nombre": "Delegación de prueba", "zona": "Urbana", "comuna": "La Serena",
                           "direccion": "Calle de prueba 123", "telefono": "51 2 200 999",
                           "horario": "Lun a vie · 09:00 a 13:00", "delegado": ""},
            "territorio": {"nombre": "Unidad vecinal de prueba", "delegacion": self.del1.pk,
                           "descripcion": "Sector creado por la prueba automática."},
            "usuario": {"rut": rut(1), "nombres": "Paula Andrea", "apellidos": "Prueba Soto",
                        "correo": "paula.prueba@ejemplo.cl", "cargo": "Apoyo",
                        "cargo_asignado": "", "delegacion": self.del1.pk,
                        "rol": Rol.objects.get(nombre="Consulta").pk},
            "cargo": {"nombre": "Cargo creado en la prueba",
                      "descripcion": "Un cargo para comprobar el CRUD completo.", "funciones": ""},
            "rol": {"nombre": "Rol creado en la prueba",
                    "descripcion": "Un rol para comprobar el CRUD completo."},
            "vecino": {"rut": rut(2), "nombres": "Ana", "apellidos": "Prueba Díaz",
                       "telefono": "9 1234 5678", "correo": "ana.prueba@ejemplo.cl",
                       "direccion": "Calle Uno 22", "territorio": self.ter1.pk},
            "junta": {"nombre": "Junta creada en la prueba", "delegacion": self.del1.pk,
                      "territorio": Territorio.objects.get(codigo="TER-02").pk,
                      "direccion": "Pasaje Dos 33", "fecha_constitucion": "2020-01-15"},
            "participacion": {"vecino": Solicitante.objects.get(nombres="Elena").pk,
                              "junta": JuntaVecinos.objects.get(codigo="JV-02").pk,
                              "cargo": "socio", "fecha_incorporacion": "2021-03-01"},
            "hito": {"nombre": "Hito creado en la prueba", "descripcion": "Una jornada para comprobar el CRUD.",
                     "periodicidad": "unica", "fecha_inicio": str(hoy), "fecha_termino": str(hoy + timedelta(days=1)),
                     "delegacion": self.del1.pk, "territorio": self.ter1.pk,
                     "responsables": [self.marcela.pk]},
            "actividad": {"funcionario": self.marcela.pk, "delegacion": self.del1.pk,
                          "asignacion": meta_cargo.pk, "fecha": str(hoy - timedelta(days=1)),
                          "cantidad": 1, "tipo": "terreno", "accion": "Actividad creada en la prueba",
                          "detalle": "Detalle suficiente para el verificador.", "origen": "planificada",
                          "territorio": self.ter1.pk, "avance": 50, "responsable": "",
                          "fecha_compromiso": str(hoy + timedelta(days=5))},
            "gestion_social": {"beneficiario": Solicitante.objects.get(nombres="Elena").pk,
                               "tipo": sat01.tipo_atencion_id, "subtipo": sat01.pk,
                               "delegacion": self.del1.pk,
                               "detalle": "Pide ayuda alimentaria; se abre el caso de prueba.",
                               "documento": "Informe social de prueba",
                               "fecha_atencion": str(hoy - timedelta(days=2)),
                               "ingreso": str(hoy - timedelta(days=1)),
                               "responsable": self.marcela.pk, "devoluciones": 0},
            "tipo": {"nombre": "Tipo creado en la prueba", "area": "Social",
                     "descripcion": "Un tipo para comprobar el CRUD completo."},
            "subtipo": {"tipo_atencion": TipoAtencion.objects.get(codigo="TAT-01").pk,
                        "nombre": "Subtipo creado en la prueba",
                        "descripcion": "Un subtipo para comprobar el CRUD completo."},
            "meta": {"nombre": "Meta creada en la prueba", "area": "Social",
                     "descripcion": "Una meta para comprobar el CRUD completo.",
                     "medicion": "actividades", "unidad": "Cantidad",
                     "requiere_evidencia": "on", "evidencia_requerida": "Acta firmada"},
            "asignacion": {"periodo": Periodo.objects.get(codigo="PER-D02").pk,
                           "item": Item.objects.get(codigo="ITM-01").pk,
                           "cargo": Cargo.objects.get(codigo="CAR-01").pk, "funcionario": "",
                           "meta": 10, "ponderador": 20, "observacion": ""},
            "evidencia": {"origen": "actividad", "actividad": Actividad.objects.get(codigo="ACT-E002").pk,
                          "tipo": "acta", "descripcion": "Acta de la inspección de prueba",
                          "referencia": "Folio 1001", "observacion": ""},
            "trimestre": {"nombre": "Trimestre creado en la prueba", "anio": 2027, "numero": 3,
                          "inicio": "2027-07-01", "termino": "2027-09-30", "observacion": ""},
        }[clave]


# Para cada entidad: nombre de la URL de creación, edición y baja, y el campo
# que se cambia al editar.
RUTAS = {
    "delegacion": ("organizacion:delegacion_nueva", "organizacion:delegacion_editar",
                   "organizacion:delegacion_estado", "nombre"),
    "territorio": ("organizacion:territorio_nuevo", "organizacion:territorio_editar",
                   "organizacion:territorio_estado", "nombre"),
    "usuario": ("organizacion:usuario_nuevo", "organizacion:usuario_editar",
                "organizacion:usuario_estado", "cargo"),
    "cargo": ("gestion:cargo_nuevo", "gestion:cargo_editar", "gestion:cargo_estado", "nombre"),
    "rol": ("organizacion:rol_nuevo", "organizacion:rol_editar", "organizacion:rol_estado", "nombre"),
    "vecino": ("atencion:vecino_nuevo", "atencion:vecino_editar", "atencion:vecino_estado", "nombres"),
    "junta": ("atencion:junta_nueva", "atencion:junta_editar", "atencion:junta_estado", "nombre"),
    "participacion": ("atencion:participacion_nueva", "atencion:participacion_editar",
                      "atencion:participacion_estado", "fecha_incorporacion"),
    "hito": ("gestion:hito_nuevo", "gestion:hito_editar", "gestion:hito_estado", "nombre"),
    "actividad": ("gestion:registro_actividad_nueva", "gestion:registro_actividad_editar",
                  "gestion:registro_actividad_anular", "accion"),
    "gestion_social": ("atencion:gestion_nueva", "atencion:gestion_editar",
                       "atencion:gestion_anular", "derivacion"),
    "tipo": ("catalogos:tipo_nuevo", "catalogos:tipo_editar", "catalogos:tipo_estado", "nombre"),
    "subtipo": ("catalogos:subatencion_nueva", "catalogos:subatencion_editar",
                "catalogos:subatencion_estado", "nombre"),
    "meta": ("catalogos:item_nuevo", "catalogos:item_editar", "catalogos:item_estado", "nombre"),
    "asignacion": ("gestion:meta_nueva", "gestion:meta_editar", "gestion:meta_estado", "observacion"),
    "evidencia": ("gestion:registro_evidencia_nueva", "gestion:registro_evidencia_editar",
                  "gestion:registro_evidencia_anular", "descripcion"),
    "trimestre": ("gestion:periodo_nuevo", "gestion:periodo_editar", "gestion:periodo_estado", "nombre"),
}

DETALLE = {
    "delegacion": "organizacion:delegacion_detalle", "territorio": "organizacion:territorio_detalle",
    "usuario": "organizacion:usuario_detalle", "cargo": "gestion:cargo_detalle",
    "rol": "organizacion:rol_detalle", "vecino": "atencion:vecino_detalle",
    "junta": "atencion:junta_detalle", "participacion": "atencion:participacion_detalle",
    "hito": "gestion:hito_detalle", "actividad": "gestion:registro_actividad",
    "gestion_social": "atencion:gestion_detalle", "tipo": "catalogos:tipo_detalle",
    "subtipo": "catalogos:subatencion_detalle", "meta": "catalogos:item_detalle",
    "asignacion": "gestion:meta_detalle", "evidencia": "gestion:registro_evidencia",
    "trimestre": "gestion:periodo_detalle",
}

VALOR_EDITADO = {
    "fecha_incorporacion": "2021-04-01",
    "derivacion": "Programa de prueba editado",
    "observacion": "Editado por la prueba",
}


def modelo_de(entidad):
    from django.apps import apps

    return apps.get_model(entidad.app, entidad.modelo)


def anulado(obj):
    if isinstance(obj, Actividad):
        return obj.estado == Actividad.Estado.ANULADA
    if isinstance(obj, CasoSocial):
        return obj.estado == CasoSocial.Estado.ANULADO
    if isinstance(obj, Evidencia):
        return obj.anulada
    return not obj.activo


class CrudDeLas17(Base):
    """Crear, listar, ver, editar y eliminar o desactivar, entidad por entidad."""

    def test_son_17(self):
        self.assertEqual(len(ENTIDADES), 17)
        self.assertEqual(set(RUTAS), {e.clave for e in ENTIDADES})

    def test_crud_completo_con_gestion(self):
        for entidad in ENTIDADES:
            with self.subTest(entidad=entidad.nombre):
                self._crud(entidad)

    def _crud(self, entidad):
        Modelo = modelo_de(entidad)
        nueva, editar, baja, campo = RUTAS[entidad.clave]
        datos = self.datos(entidad.clave)
        antes = Modelo.objects.count()

        # crear
        r = self.gestion.post(reverse(nueva), datos)
        self.assertEqual(r.status_code, 302, f"crear {entidad.nombre}: {self._errores(r)}")
        self.assertEqual(Modelo.objects.count(), antes + 1)
        obj = Modelo.objects.order_by("-pk").first()

        # listar (con búsqueda) y ver la ficha
        self.assertEqual(self.gestion.get(reverse(entidad.url_lista)).status_code, 200)
        self.assertEqual(self.gestion.get(reverse(entidad.url_lista) + "?q=prueba").status_code, 200)
        self.assertEqual(self.gestion.get(reverse(DETALLE[entidad.clave], args=[obj.pk])).status_code, 200)

        # editar: el mismo identificador, sin duplicar
        valor = VALOR_EDITADO.get(campo, f"{datos.get(campo, '')} (editado)")
        r = self.gestion.post(reverse(editar, args=[obj.pk]), dict(datos, **{campo: valor}))
        self.assertEqual(r.status_code, 302, f"editar {entidad.nombre}: {self._errores(r)}")
        self.assertEqual(Modelo.objects.count(), antes + 1)
        obj.refresh_from_db()
        self.assertEqual(str(getattr(obj, campo)), valor if campo != "cargo" else valor)

        # eliminar: desactivar o anular, por POST
        if entidad.estrategia == "anular":
            self.assertEqual(self.gestion.get(reverse(baja, args=[obj.pk])).status_code, 200)
            obj.refresh_from_db()
            self.assertFalse(anulado(obj), "mostrar la confirmación no anula")
            r = self.gestion.post(reverse(baja, args=[obj.pk]), {"motivo": "Anulado por la prueba automática."})
        else:
            r = self.gestion.post(reverse(baja, args=[obj.pk]), {"activar": "0"})
        self.assertEqual(r.status_code, 302)
        obj.refresh_from_db()
        self.assertTrue(anulado(obj), f"{entidad.nombre} quedó desactivado o anulado")
        self.assertEqual(Modelo.objects.count(), antes + 1, "no se borra: se conserva")

    @staticmethod
    def _errores(r):
        ctx = getattr(r, "context", None)
        if ctx and "form" in ctx:
            return dict(ctx["form"].errors)
        return r.status_code


class Permisos(Base):
    def test_consulta_ve_las_17_y_no_modifica(self):
        for entidad in ENTIDADES:
            with self.subTest(entidad=entidad.nombre):
                Modelo = modelo_de(entidad)
                obj = Modelo.objects.first()
                nueva, editar, baja, _ = RUTAS[entidad.clave]
                self.assertEqual(self.consulta.get(reverse(entidad.url_lista)).status_code, 200)
                self.assertEqual(self.consulta.get(reverse(DETALLE[entidad.clave], args=[obj.pk])).status_code, 200)
                self.assertEqual(self.consulta.get(reverse(nueva)).status_code, 403)
                self.assertEqual(self.consulta.get(reverse(editar, args=[obj.pk])).status_code, 403)
                antes = Modelo.objects.count()
                self.assertEqual(self.consulta.post(reverse(nueva), self.datos(entidad.clave)).status_code, 403)
                self.assertEqual(Modelo.objects.count(), antes)
                self.assertIn(self.consulta.post(reverse(baja, args=[obj.pk]),
                                                 {"activar": "0", "motivo": "x" * 20}).status_code, (403,))

    def test_botones_siguen_al_permiso(self):
        h = self.consulta.get(reverse("organizacion:territorios")).content.decode()
        self.assertNotIn("Nuevo territorio", h)
        self.assertNotIn(">Desactivar<", h)
        h = self.gestion.get(reverse("organizacion:territorios")).content.decode()
        self.assertIn("Nuevo territorio", h)

    def test_sin_sesion_va_al_login(self):
        anonimo = Client()
        for entidad in ENTIDADES:
            with self.subTest(entidad=entidad.nombre):
                r = anonimo.get(reverse(entidad.url_lista))
                self.assertEqual(r.status_code, 302)
                self.assertIn(reverse("cuenta:login"), r["Location"])

    def test_404_para_identificador_inexistente(self):
        for entidad in ENTIDADES:
            with self.subTest(entidad=entidad.nombre):
                _, editar, _, _ = RUTAS[entidad.clave]
                self.assertEqual(self.gestion.get(reverse(editar, args=[999999])).status_code, 404)
                self.assertEqual(self.gestion.get(reverse(DETALLE[entidad.clave], args=[999999])).status_code, 404)

    def test_get_no_modifica_y_csrf_obligatorio(self):
        ter = Territorio.objects.get(codigo="TER-07")
        self.assertEqual(self.gestion.get(reverse("organizacion:territorio_estado", args=[ter.pk])).status_code, 405)
        ter.refresh_from_db()
        self.assertTrue(ter.activo)
        con_csrf = Client(enforce_csrf_checks=True)
        con_csrf.force_login(U.objects.get(email="gestion@ejemplo.cl"))
        r = con_csrf.post(reverse("organizacion:territorio_estado", args=[ter.pk]), {"activar": "0"})
        self.assertEqual(r.status_code, 403)
        ter.refresh_from_db()
        self.assertTrue(ter.activo)

    def test_grupos_de_django(self):
        from django.contrib.auth.models import Group

        self.assertEqual(Group.objects.get(name="Consulta").permissions.count(), 17)
        self.assertEqual(Group.objects.get(name="Gestión").permissions.count(), 68)
        consulta = U.objects.get(email="consulta@ejemplo.cl")
        self.assertTrue(consulta.has_perm("gestion.view_hito"))
        self.assertFalse(consulta.has_perm("gestion.add_hito"))


class SinAutoasignacion(Base):
    def test_nadie_cambia_su_propio_rol(self):
        perfil = PerfilUsuario.objects.get(usuario__email="gestion@ejemplo.cl")
        admin = Rol.objects.get(nombre="Administrador")
        datos = {"rut": perfil.rut, "nombres": "Tomás", "apellidos": "Gallardo",
                 "correo": "gestion@ejemplo.cl", "cargo": "x", "cargo_asignado": "",
                 "delegacion": perfil.delegacion_id, "rol": admin.pk}
        self.gestion.post(reverse("organizacion:usuario_editar", args=[perfil.pk]), datos)
        perfil.refresh_from_db()
        self.assertEqual(perfil.rol.nombre, "Gestión")

    def test_gestion_no_asigna_roles_con_mas_poder(self):
        datos = dict(self.datos("usuario"), rol=Rol.objects.get(nombre="Administrador").pk)
        r = self.gestion.post(reverse("organizacion:usuario_nuevo"), datos)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(PerfilUsuario.objects.filter(usuario__email="paula.prueba@ejemplo.cl").exists())

    def test_gestion_no_administra_privilegios(self):
        rol = Rol.objects.get(nombre="Funcionario")
        self.assertEqual(self.gestion.get(reverse("organizacion:rol_privilegios", args=[rol.pk])).status_code, 403)
        r = self.gestion.post(reverse("organizacion:rol_privilegios", args=[rol.pk]),
                              {"alcance": "todas", "permisos": ["gestionar_usuario"]})
        self.assertEqual(r.status_code, 403)
        rol.refresh_from_db()
        self.assertNotIn("gestionar_usuario", rol.permisos)

    def test_nadie_se_desactiva_a_si_mismo(self):
        admin = self._cliente("felipe.araya@ejemplo.cl")
        perfil = PerfilUsuario.objects.get(usuario__email="felipe.araya@ejemplo.cl")
        admin.post(reverse("organizacion:usuario_estado", args=[perfil.pk]), {"activar": "0"})
        perfil.refresh_from_db()
        self.assertTrue(perfil.activo)

    def test_el_formulario_general_no_trae_privilegios(self):
        h = self.gestion.get(reverse("organizacion:usuario_nuevo")).content.decode()
        self.assertNotIn('name="is_superuser"', h)
        self.assertNotIn('name="is_staff"', h)
        self.assertNotIn('name="password', h)
        h = self.gestion.get(reverse("organizacion:rol_nuevo")).content.decode()
        self.assertNotIn('name="permisos"', h)
        self.assertNotIn('name="grupo"', h)


class Validaciones(Base):
    """Un formulario inválido muestra el error y no guarda nada."""

    def _rechaza(self, ruta, datos, Modelo, texto, args=None):
        antes = Modelo.objects.count()
        r = self.gestion.post(reverse(ruta, args=args or []), datos)
        self.assertEqual(r.status_code, 200)
        self.assertIn(texto, r.content.decode())
        self.assertEqual(Modelo.objects.count(), antes)
        return r

    def test_trimestre_numero_y_fechas(self):
        self._rechaza("gestion:periodo_nuevo", dict(self.datos("trimestre"), numero=5), Periodo, "1 al 4")
        self._rechaza("gestion:periodo_nuevo", dict(self.datos("trimestre"), termino="2027-06-01"),
                      Periodo, "no puede ser anterior al inicio")

    def test_asignacion_objetivo_y_ponderacion(self):
        self._rechaza("gestion:meta_nueva", dict(self.datos("asignacion"), meta=0), MetaPeriodo, "mayor que cero")
        self._rechaza("gestion:meta_nueva", dict(self.datos("asignacion"), ponderador=150), MetaPeriodo, "100")

    def test_relaciones_coherentes(self):
        otra = Territorio.objects.get(codigo="TER-04")  # es de DEL-02
        self._rechaza("atencion:junta_nueva", dict(self.datos("junta"), territorio=otra.pk),
                      JuntaVecinos, "misma delegación")
        sub_otro_tipo = SubAtencion.objects.exclude(tipo_atencion__codigo="TAT-01").filter(activo=True).first()
        self._rechaza("atencion:gestion_nueva", dict(self.datos("gestion_social"), subtipo=sub_otro_tipo.pk),
                      CasoSocial, "pertenece a")

    def test_fecha_de_compromiso_no_anterior(self):
        datos = self.datos("actividad")
        datos["fecha_compromiso"] = str(self.hoy - timedelta(days=10))
        self._rechaza("gestion:registro_actividad_nueva", datos, Actividad, "fecha de compromiso")

    def test_codigos_y_rut_unicos_y_correo(self):
        existente = Solicitante.objects.first()
        self._rechaza("atencion:vecino_nuevo", dict(self.datos("vecino"), rut=existente.rut),
                      Solicitante, "Ya hay un vecino con ese RUT")
        self._rechaza("atencion:vecino_nuevo", dict(self.datos("vecino"), rut="12345678-9"),
                      Solicitante, "RUT no es válido")
        self._rechaza("atencion:vecino_nuevo", dict(self.datos("vecino"), correo="no-es-correo"),
                      Solicitante, "correo")

    def test_conserva_lo_ingresado(self):
        r = self._rechaza("gestion:periodo_nuevo", dict(self.datos("trimestre"), numero=5), Periodo, "1 al 4")
        self.assertIn("Trimestre creado en la prueba", r.content.decode())


class RelacionesProtegidas(Base):
    def test_territorio_con_vecinos_no_se_desactiva(self):
        self.gestion.post(reverse("organizacion:territorio_estado", args=[self.ter1.pk]), {"activar": "0"})
        self.ter1.refresh_from_db()
        self.assertTrue(self.ter1.activo)

    def test_junta_con_participantes_no_se_desactiva(self):
        junta = JuntaVecinos.objects.get(codigo="JV-01")
        self.gestion.post(reverse("atencion:junta_estado", args=[junta.pk]), {"activar": "0"})
        junta.refresh_from_db()
        self.assertTrue(junta.activo)

    def test_cancelar_no_modifica(self):
        act = Actividad.objects.get(codigo="ACT-E002")
        h = self.gestion.get(reverse("gestion:registro_actividad_anular", args=[act.pk])).content.decode()
        self.assertIn("Cancelar", h)
        act.refresh_from_db()
        self.assertEqual(act.estado, Actividad.Estado.BORRADOR)

    def test_evidencia_de_un_solo_origen(self):
        datos = dict(self.datos("evidencia"), origen="caso", caso="")
        antes = Evidencia.objects.count()
        r = self.gestion.post(reverse("gestion:registro_evidencia_nueva"), datos)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Evidencia.objects.count(), antes)


class Sesion(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_datos_demo", verbosity=0, stdout=open(os.devnull, "w"))

    def test_login_logout(self):
        c = Client()
        r = c.post(reverse("cuenta:login"), {"username": "consulta@ejemplo.cl", "password": "mala"})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("_auth_user_id", c.session)
        r = c.post(reverse("cuenta:login"), {"username": "consulta@ejemplo.cl",
                                             "password": os.environ["SGR_DEMO_PASSWORD"]})
        self.assertEqual(r.status_code, 302)
        self.assertIn("_auth_user_id", c.session)
        self.assertEqual(c.get(reverse("cuenta:logout")).status_code, 405)
        c.post(reverse("cuenta:logout"))
        r = c.get(reverse("organizacion:territorios"))
        self.assertEqual(r.status_code, 302)

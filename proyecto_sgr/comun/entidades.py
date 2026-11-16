"""
Las 17 entidades de la Evaluación 3 y sus permisos de Django.

Es la tabla que une cada entidad del enunciado con su modelo, su pantalla y
sus permisos. La usan:

* el motor de mantenedores, para saber qué permiso de Django pedir en cada
  vista (``view`` para listar y ver, ``add`` para crear, ``change`` para
  editar, ``delete`` para desactivar o anular);
* la migración y la señal que arman los grupos **Consulta** y **Gestión**;
* el menú lateral y el panel, para mostrar solo lo que cada quien puede ver;
* las pruebas, que recorren las 17 una por una.

Dos caminos de acceso, a propósito
----------------------------------
Cada entidad se abre con su **permiso de Django** *o* con la **acción de
negocio** del SGR que ya la administraba (``clave_negocio``). Los roles
operativos del Proyecto Integrado —Funcionario, Verificador, Delegado,
Coordinador— siguen funcionando con sus acciones; los perfiles de prueba
Consulta y Gestión, y el Administrador, entran con los permisos de Django
de su grupo. Ninguno de los dos caminos se salta en el servidor: la vista
comprueba uno u otro antes de responder, y sin ninguno responde 403.

Las entidades sin acción de negocio (actividades, gestiones sociales y
evidencias como registros completos) se abren solo con permisos de Django:
el flujo operativo de esas tres tiene sus propias pantallas.
"""

from dataclasses import dataclass

from comun import permisos as P

#: Las cuatro operaciones del CRUD y el permiso de Django que piden.
ACCIONES = {
    "view": "consultar",
    "add": "crear",
    "change": "editar",
    "delete": "desactivar o anular",
}


@dataclass(frozen=True)
class Entidad:
    clave: str             # identificador interno y nombre en el menú
    nombre: str            # como la llama el enunciado
    app: str               # app_label de Django
    modelo: str            # model_name de Django (en minúsculas)
    clave_negocio: str     # acción del SGR que también la administra, o ""
    url_lista: str         # nombre de la URL del listado
    estrategia: str        # cómo se elimina: «desactivar» o «anular»

    def permiso(self, accion):
        """El permiso de Django completo, por ejemplo «gestion.view_hito»."""
        return f"{self.app}.{accion}_{self.modelo}"

    def codename(self, accion):
        return f"{accion}_{self.modelo}"


ENTIDADES = (
    Entidad("delegacion", "Delegación", "organizacion", "delegacion",
            P.GESTIONAR_USUARIO, "organizacion:delegaciones", "desactivar"),
    Entidad("territorio", "Territorio", "organizacion", "territorio",
            P.GESTIONAR_USUARIO, "organizacion:territorios", "desactivar"),
    Entidad("usuario", "Usuario funcionario", "organizacion", "perfilusuario",
            P.GESTIONAR_USUARIO, "organizacion:usuarios", "desactivar"),
    Entidad("cargo", "Cargo", "gestion", "cargo",
            P.DEFINIR_META, "gestion:cargos", "desactivar"),
    Entidad("rol", "Rol", "organizacion", "rol",
            P.GESTIONAR_USUARIO, "organizacion:roles", "desactivar"),
    Entidad("vecino", "Vecino", "atencion", "solicitante",
            P.REGISTRAR_ATENCION, "atencion:vecinos", "desactivar"),
    Entidad("junta", "Junta de vecinos", "atencion", "juntavecinos",
            P.REGISTRAR_ATENCION, "atencion:juntas", "desactivar"),
    Entidad("participacion", "Participación en junta", "atencion", "participacionjunta",
            P.REGISTRAR_ATENCION, "atencion:participaciones", "desactivar"),
    Entidad("hito", "Hito", "gestion", "hito",
            P.CONFIGURAR_PERIODO, "gestion:hitos", "desactivar"),
    Entidad("actividad", "Actividad", "gestion", "actividad",
            "", "gestion:registro_actividades", "anular"),
    Entidad("gestion_social", "Gestión social", "atencion", "casosocial",
            "", "atencion:gestiones", "anular"),
    Entidad("tipo", "Tipo de atención", "catalogos", "tipoatencion",
            P.GESTIONAR_CATALOGO, "catalogos:tipos", "desactivar"),
    Entidad("subtipo", "Subtipo de atención", "catalogos", "subatencion",
            P.GESTIONAR_CATALOGO, "catalogos:subatenciones", "desactivar"),
    Entidad("meta", "Meta", "catalogos", "item",
            P.GESTIONAR_CATALOGO, "catalogos:items", "desactivar"),
    Entidad("asignacion", "Asignación de meta", "gestion", "metaperiodo",
            P.DEFINIR_META, "gestion:metas", "desactivar"),
    Entidad("evidencia", "Evidencia", "gestion", "evidencia",
            "", "gestion:registro_evidencias", "anular"),
    Entidad("trimestre", "Trimestre", "gestion", "periodo",
            P.CONFIGURAR_PERIODO, "gestion:periodos", "desactivar"),
)

POR_CLAVE = {e.clave: e for e in ENTIDADES}
POR_MODELO = {(e.app, e.modelo): e for e in ENTIDADES}

#: Los dos grupos de Django de los perfiles de prueba, con sus acciones.
GRUPOS = {
    "Consulta": ("view",),
    "Gestión": ("view", "add", "change", "delete"),
}


def de_modelo(modelo):
    """La entidad de un modelo, o None si el modelo no es una de las 17."""
    if modelo is None:
        return None
    meta = modelo._meta
    return POR_MODELO.get((meta.app_label, meta.model_name))


def puede(usuario, entidad, accion):
    """
    True si esa persona puede hacer esa operación sobre esa entidad.

    Pasa con el permiso de Django de la operación o con la acción de negocio
    que administra la entidad. ``tiene_permiso`` ya descarta a quien no
    inició sesión y deja pasar al superusuario.
    """
    if isinstance(entidad, str):
        entidad = POR_CLAVE[entidad]
    if entidad.clave_negocio and P.tiene_permiso(usuario, entidad.clave_negocio):
        return True
    return P.tiene_permiso(usuario, entidad.permiso(accion))


def visibles(usuario):
    """Diccionario clave → True/False: qué entidades puede consultar."""
    return {e.clave: puede(usuario, e, "view") for e in ENTIDADES}

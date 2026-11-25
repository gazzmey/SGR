"""
Defectos DEF-02 y DEF-03 del protocolo de pruebas (casos CAT-04 y CAT-02).

* DEF-03: un nombre repetido con otras mayúsculas, tildes o espacios se
  aceptaba como distinto. Ahora se rechaza en todos los catálogos con
  nombre único.
* DEF-02: renombrar un subtipo (o tipo) con atenciones registradas cambiaba
  cómo se leían las atenciones anteriores. Ahora el nombre queda fijo.
"""

from atencion.models import Atencion
from catalogos.forms import ItemForm, SubAtencionForm, TipoAtencionForm
from catalogos.models import SubAtencion, TipoAtencion
from comun.nombres import normalizar
from gestion.forms import CargoForm
from organizacion.forms import DelegacionForm, RolForm
from organizacion.models import Delegacion

from pruebas.test_evaluacion3 import Base

DESCRIPCION = "Descripción suficientemente larga para la prueba."


class NombresSinRepetir(Base):
    def test_normalizar(self):
        self.assertEqual(normalizar("  Las   COMPAÑÍAS "), "las companias")
        self.assertEqual(normalizar("Asistencia social"), normalizar("ASISTENCIA SOCIAL"))

    def test_tipo_de_atencion_con_otra_escritura(self):
        existente = TipoAtencion.objects.get(codigo="TAT-01")
        variante = existente.nombre.upper().replace("Ó", "O").replace("Í", "I")
        f = TipoAtencionForm({"nombre": variante, "area": "Social", "descripcion": DESCRIPCION})
        self.assertFalse(f.is_valid())
        self.assertIn("Ya existe", f.errors["nombre"][0])
        self.assertIn(existente.codigo, f.errors["nombre"][0])

    def test_delegacion_rol_item_y_cargo(self):
        d1 = Delegacion.objects.get(codigo="DEL-01")
        f = DelegacionForm({"nombre": d1.nombre.upper(), "zona": "Urbana", "comuna": "La Serena",
                            "telefono": "+56 51 220 0009"})
        self.assertFalse(f.is_valid())
        self.assertIn("nombre", f.errors)
        f = RolForm({"nombre": "  funcionario ", "descripcion": ""})
        self.assertFalse(f.is_valid())
        self.assertIn("nombre", f.errors)
        from catalogos.models import Item
        item = Item.objects.first()
        f = ItemForm({"nombre": item.nombre.lower(), "area": "Territorial", "medicion": "actividades",
                      "unidad": "Cantidad"})
        self.assertFalse(f.is_valid())
        self.assertIn("nombre", f.errors)
        from gestion.models import Cargo
        cargo = Cargo.objects.first()
        f = CargoForm({"nombre": cargo.nombre.upper(), "descripcion": "x"})
        self.assertFalse(f.is_valid())
        self.assertIn("nombre", f.errors)

    def test_editar_sin_cambiar_el_nombre_sigue_valiendo(self):
        t = TipoAtencion.objects.get(codigo="TAT-D09")
        f = TipoAtencionForm({"nombre": t.nombre, "area": t.area, "descripcion": DESCRIPCION}, instance=t)
        self.assertTrue(f.is_valid(), f.errors)

    def test_un_nombre_nuevo_si_se_acepta(self):
        f = TipoAtencionForm({"nombre": "Emergencias climáticas", "area": "Social", "descripcion": DESCRIPCION})
        self.assertTrue(f.is_valid(), f.errors)


class NombreFijoConAtenciones(Base):
    def test_el_subtipo_con_atenciones_no_cambia_de_nombre(self):
        s = SubAtencion.objects.get(codigo="SAT-01")
        self.assertTrue(Atencion.objects.filter(subatencion=s).exists())
        original = s.nombre
        f = SubAtencionForm({"tipo_atencion": s.tipo_atencion_id, "nombre": "Otro nombre cualquiera",
                             "descripcion": DESCRIPCION}, instance=s)
        self.assertTrue(f.fields["nombre"].disabled)
        self.assertIn("atenciones registradas", f.fields["nombre"].help_text)
        self.assertTrue(f.is_valid(), f.errors)
        f.save()
        s.refresh_from_db()
        self.assertEqual(s.nombre, original)
        self.assertEqual(s.descripcion, DESCRIPCION)        # la descripción sí se corrige

    def test_el_tipo_con_atenciones_no_cambia_de_nombre(self):
        t = TipoAtencion.objects.get(codigo="TAT-01")
        f = TipoAtencionForm({"nombre": "Otro", "area": t.area, "descripcion": DESCRIPCION}, instance=t)
        self.assertTrue(f.fields["nombre"].disabled)

    def test_sin_atenciones_el_nombre_se_puede_cambiar(self):
        s = SubAtencion.objects.filter(atenciones__isnull=True, activo=True).first()
        f = SubAtencionForm({"tipo_atencion": s.tipo_atencion_id, "nombre": "Nombre corregido de prueba",
                             "descripcion": DESCRIPCION}, instance=s)
        self.assertFalse(f.fields["nombre"].disabled)
        self.assertTrue(f.is_valid(), f.errors)

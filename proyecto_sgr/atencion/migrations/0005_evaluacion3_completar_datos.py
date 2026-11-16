"""
La gestión social se vincula a una asignación de meta, y se completan los
datos nuevos de vecinos y gestiones en lo que ya estaba registrado.

* El nombre del vecino, que antes era un solo campo, se reparte entre
  nombres y apellidos: con cuatro palabras o más, las dos últimas son los
  apellidos; con dos o tres, la última. Se puede corregir en la ficha.
* El sector de texto libre se convierte en territorio del catálogo, en la
  delegación donde la persona fue atendida por primera vez. Si nunca fue
  atendida no hay delegación de donde colgarlo, y el texto queda como
  referencia en «sector».
* La fecha de atención de cada gestión social es la de su atención, sin
  pasar de la fecha de ingreso del caso.
* El estado de cada gestión social sale de sus fechas.
"""

import django.db.models.deletion
from django.db import migrations, models
from django.utils import timezone


def _repartir(nombre):
    partes = (nombre or "").split()
    if len(partes) >= 4:
        return " ".join(partes[:-2]), " ".join(partes[-2:])
    if len(partes) >= 2:
        return " ".join(partes[:-1]), partes[-1]
    return nombre or "", ""


def completar(apps, schema_editor):
    Solicitante = apps.get_model("atencion", "Solicitante")
    CasoSocial = apps.get_model("atencion", "CasoSocial")
    Territorio = apps.get_model("organizacion", "Territorio")

    mayor = 0
    for codigo in Territorio.objects.values_list("codigo", flat=True):
        sufijo = codigo.split("-", 1)[-1]
        if sufijo.isdigit():
            mayor = max(mayor, int(sufijo))

    for vecino in Solicitante.objects.all():
        cambios = []
        if not vecino.apellidos:
            vecino.nombres, vecino.apellidos = _repartir(vecino.nombres)
            cambios += ["nombres", "apellidos"]
        if vecino.sector and not vecino.territorio_id:
            primera = vecino.atenciones.order_by("registrada").first()
            if primera is not None:
                territorio = Territorio.objects.filter(
                    delegacion_id=primera.delegacion_id, nombre=vecino.sector).first()
                if territorio is None:
                    mayor += 1
                    territorio = Territorio.objects.create(
                        codigo=f"TER-{mayor:02d}", nombre=vecino.sector,
                        delegacion_id=primera.delegacion_id,
                        descripcion="Creado al migrar el sector de texto libre.",
                    )
                vecino.territorio = territorio
                cambios.append("territorio")
        if cambios:
            vecino.save(update_fields=cambios)

    for caso in CasoSocial.objects.select_related("atencion"):
        atendido = timezone.localtime(caso.atencion.registrada).date()
        caso.fecha_atencion = min(atendido, caso.ingreso) if caso.ingreso else atendido
        cierre = caso.beneficio_entregado if caso.lleva_beneficio else caso.informe_entregado
        if caso.estado != "anulado":
            caso.estado = "cerrado" if cierre else "en_curso"
        caso.save(update_fields=["fecha_atencion", "estado"])


class Migration(migrations.Migration):

    dependencies = [
        ("atencion", "0004_evaluacion3_vecinos_y_juntas"),
        ("gestion", "0016_evaluacion3_hitos_y_asignaciones"),
    ]

    operations = [
        migrations.AddField(
            model_name="casosocial", name="asignacion",
            field=models.ForeignKey(
                blank=True, null=True,
                help_text="La meta a la que aporta esta gestión. Opcional.",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="gestiones_sociales", to="gestion.metaperiodo",
                verbose_name="asignación de meta"),
        ),
        migrations.RunPython(completar, migrations.RunPython.noop),
    ]

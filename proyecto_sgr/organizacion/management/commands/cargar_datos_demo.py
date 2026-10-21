"""
Carga los datos ficticios con los que se revisa el sistema.

**Todos los datos son inventados.** No hay nombres, correos, RUT ni
antecedentes de personas reales: los correos usan el dominio reservado
``ejemplo.cl`` y los RUT son números con dígito verificador válido que no
corresponden a nadie. Los sectores de La Serena se usan como referencia
territorial.

Son los mismos datos de la maqueta aprobada, para que las pantallas en Django
muestren exactamente lo que se revisó: 18 delegaciones, 6 roles, 14 usuarios,
10 ítems, 8 tipos de atención, 24 subatenciones y unas pocas atenciones
registradas.

El comando se puede ejecutar varias veces sin duplicar nada: cada registro se
busca por su código —o por su correo, en el caso de los usuarios— antes de
crearse.

    python manage.py cargar_datos_demo

Dos cosas que conviene saber antes de preguntar
-----------------------------------------------
1. **Las contraseñas de demostración.** Las cuentas se crean con una
   contraseña común para poder entrar y revisar. Se puede cambiar con la
   variable de entorno ``SGR_DEMO_PASSWORD``. Son cuentas ficticias de un
   sistema de prueba; en una instalación real este comando no se ejecuta, y
   las cuentas nacen sin contraseña utilizable desde el mantenedor de
   usuarios.

2. **Un rol por usuario.** La maqueta contemplaba personas con dos roles
   —quien verifica y a la vez conduce la delegación—. El modelo
   ``PerfilUsuario`` tiene un solo rol, tal como quedó en la Unidad 2 de
   Back End, así que aquí se asigna el primero y el segundo queda anotado en
   el campo ``cargo``. Convertir ``rol`` en una relación de muchos a muchos
   es trabajo de la próxima entrega: cambiaría el esquema que la entrega
   anterior ya usa.

Las fechas de creación se escriben con ``update()`` y no al crear el registro,
porque ``creada`` es un campo ``auto_now_add``: Django pone la fecha del día
y descarta cualquier valor que se le pase. Son solo presentación, para que los
listados muestren un historial verosímil.
"""

import os
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from atencion.models import Atencion, Solicitante
from catalogos.models import Item, SubAtencion, TipoAtencion
from gestion.models import Cargo, MetaPeriodo, Periodo
from gestion.modelos_actividad import Actividad, Evidencia
from gestion.modelos_agenda import CambioCompromiso, Compromiso
from gestion.reglas import PROPUESTA_DEL_PLAN, ReglaCalculo
from organizacion.models import Delegacion, PerfilUsuario, Rol

CLAVE_DEMO = os.environ.get("SGR_DEMO_PASSWORD", "Demo.Sgr2026")

DELEGACIONES = [{'codigo': 'DEL-01',
  'nombre': 'Las Compañías',
  'zona': 'Urbana',
  'direccion': 'Av. Pedro Pablo Muñoz 1450',
  'comuna': 'La Serena',
  'telefono': '51 2 200 101',
  'horario': 'Lun a vie · 08:30 a 14:00',
  'activo': True,
  'creada': '2024-01-12',
  'desactivada': None},
 {'codigo': 'DEL-02',
  'nombre': 'La Antena',
  'zona': 'Urbana',
  'direccion': 'Calle Los Aromos 230',
  'comuna': 'La Serena',
  'telefono': '51 2 200 102',
  'horario': 'Lun a vie · 09:00 a 14:00',
  'activo': True,
  'creada': '2024-01-12',
  'desactivada': None},
 {'codigo': 'DEL-03',
  'nombre': 'Coquimbito',
  'zona': 'Rural',
  'direccion': 'Camino a Coquimbito 88',
  'comuna': 'La Serena',
  'telefono': '51 2 200 103',
  'horario': 'Lun, mié y vie · 09:00 a 13:00',
  'activo': True,
  'creada': '2024-03-03',
  'desactivada': None},
 {'codigo': 'DEL-04',
  'nombre': 'El Milagro',
  'zona': 'Rural',
  'direccion': 'Ruta D-435, kilómetro 3',
  'comuna': 'La Serena',
  'telefono': '51 2 200 104',
  'horario': 'Mar y jue · 09:00 a 13:00',
  'activo': True,
  'creada': '2024-03-03',
  'desactivada': None},
 {'codigo': 'DEL-05',
  'nombre': 'Lambert',
  'zona': 'Rural',
  'direccion': 'Plaza de Lambert s/n',
  'comuna': 'La Serena',
  'telefono': '51 2 200 105',
  'horario': 'Mié · 09:00 a 13:00',
  'activo': True,
  'creada': '2024-03-03',
  'desactivada': None},
 {'codigo': 'DEL-06',
  'nombre': 'Islón',
  'zona': 'Rural',
  'direccion': 'Camino a Islón 1200',
  'comuna': 'La Serena',
  'telefono': '51 2 200 106',
  'horario': 'Lun y jue · 09:00 a 13:00',
  'activo': True,
  'creada': '2024-03-03',
  'desactivada': None},
 {'codigo': 'DEL-07',
  'nombre': 'Las Rojas',
  'zona': 'Urbana',
  'direccion': 'Av. Las Rojas 2890',
  'comuna': 'La Serena',
  'telefono': '51 2 200 107',
  'horario': 'Lun a vie · 08:30 a 14:00',
  'activo': True,
  'creada': '2024-01-12',
  'desactivada': None},
 {'codigo': 'DEL-08',
  'nombre': 'Gabriela Mistral',
  'zona': 'Urbana',
  'direccion': 'Pasaje Los Nogales 45',
  'comuna': 'La Serena',
  'telefono': '51 2 200 108',
  'horario': 'Lun a vie · 09:00 a 14:00',
  'activo': True,
  'creada': '2024-05-20',
  'desactivada': None},
 {'codigo': 'DEL-09',
  'nombre': 'Altovalsol',
  'zona': 'Rural',
  'direccion': 'Camino a Altovalsol 3400',
  'comuna': 'La Serena',
  'telefono': '51 2 200 109',
  'horario': 'Mar y vie · 09:00 a 13:00',
  'activo': True,
  'creada': '2024-05-20',
  'desactivada': None},
 {'codigo': 'DEL-10',
  'nombre': 'Algarrobito',
  'zona': 'Rural',
  'direccion': 'Calle Principal 115',
  'comuna': 'La Serena',
  'telefono': '51 2 200 110',
  'horario': 'Jue · 09:00 a 13:00',
  'activo': True,
  'creada': '2026-07-08',
  'desactivada': None},
 {'codigo': 'DEL-11',
  'nombre': 'Centro Histórico',
  'zona': 'Urbana',
  'direccion': 'Calle Prat 451, oficina 3',
  'comuna': 'La Serena',
  'telefono': '51 2 200 111',
  'horario': 'Lun a vie · 08:30 a 17:00',
  'activo': True,
  'creada': '2024-01-12',
  'desactivada': None},
 {'codigo': 'DEL-12',
  'nombre': 'Peñuelas Norte',
  'zona': 'Costera',
  'direccion': 'Av. del Mar 4120',
  'comuna': 'La Serena',
  'telefono': '51 2 200 112',
  'horario': 'Lun a vie · 09:00 a 14:00',
  'activo': True,
  'creada': '2024-05-20',
  'desactivada': None},
 {'codigo': 'DEL-13',
  'nombre': 'Caleta San Pedro',
  'zona': 'Costera',
  'direccion': 'Caleta San Pedro, sitio 7',
  'comuna': 'La Serena',
  'telefono': '51 2 200 113',
  'horario': 'Mar y jue · 09:00 a 13:00',
  'activo': True,
  'creada': '2026-09-01',
  'desactivada': None},
 {'codigo': 'DEL-14',
  'nombre': 'Cuatro Esquinas',
  'zona': 'Urbana',
  'direccion': 'Av. Cuatro Esquinas 1980',
  'comuna': 'La Serena',
  'telefono': '51 2 200 114',
  'horario': 'Lun a vie · 09:00 a 14:00',
  'activo': True,
  'creada': '2024-05-20',
  'desactivada': None},
 {'codigo': 'DEL-15',
  'nombre': 'Villa San Bartolomé',
  'zona': 'Urbana',
  'direccion': 'Calle Los Tilos 760',
  'comuna': 'La Serena',
  'telefono': '51 2 200 115',
  'horario': 'Lun a vie · 09:00 a 14:00',
  'activo': True,
  'creada': '2024-06-11',
  'desactivada': None},
 {'codigo': 'DEL-16',
  'nombre': 'El Romeral',
  'zona': 'Rural',
  'direccion': 'Ruta 5 Norte, kilómetro 476',
  'comuna': 'La Serena',
  'telefono': '51 2 200 116',
  'horario': 'Vie · 09:00 a 13:00',
  'activo': True,
  'creada': '2026-09-01',
  'desactivada': None},
 {'codigo': 'DEL-17',
  'nombre': 'Tierras Blancas Sur',
  'zona': 'Urbana',
  'direccion': 'Pasaje El Olivar 22',
  'comuna': 'La Serena',
  'telefono': '51 2 200 117',
  'horario': 'Lun a vie · 09:00 a 14:00',
  'activo': False,
  'creada': '2024-06-11',
  'desactivada': '2026-09-09'},
 {'codigo': 'DEL-18',
  'nombre': 'Oficina móvil norte',
  'zona': 'Rural',
  'direccion': 'Sin domicilio fijo · itinerante',
  'comuna': 'La Serena',
  'telefono': '51 2 200 118',
  'horario': 'Según programación mensual',
  'activo': False,
  'creada': '2025-02-04',
  'desactivada': '2026-07-31'}]

ROLES = [{'codigo': 'ROL-01',
  'nombre': 'Funcionario',
  'descripcion': 'Registra su propia gestión: actividades, compromisos y las '
                 'evidencias que las respaldan.',
  'permisos': ['registrar_actividad',
               'adjuntar_evidencia',
               'registrar_atencion'],
  'activo': True,
  'alcance': 'propia',
  'creada': '2024-01-12',
  'desactivada': None},
 {'codigo': 'ROL-02',
  'nombre': 'Verificador',
  'descripcion': 'Revisa las evidencias de su delegación y decide si '
                 'aprueban, se rechazan o vuelven a corregir.',
  'permisos': ['validar_evidencia', 'ver_tablero'],
  'activo': True,
  'alcance': 'propia',
  'creada': '2024-01-12',
  'desactivada': None},
 {'codigo': 'ROL-03',
  'nombre': 'Delegado o jefatura',
  'descripcion': 'Conduce la delegación: ve el tablero completo, reasigna '
                 'compromisos y registra ajustes.',
  'permisos': ['ver_tablero',
               'reasignar_compromiso',
               'registrar_ajuste',
               'ver_informes'],
  'activo': True,
  'alcance': 'propia',
  'creada': '2024-01-12',
  'desactivada': None},
 {'codigo': 'ROL-04',
  'nombre': 'Coordinador del sistema',
  'descripcion': 'Define cómo se mide: períodos, metas, ponderadores y '
                 'umbrales del semáforo.',
  'permisos': ['configurar_periodo',
               'definir_meta',
               'ver_informes',
               'ver_tablero',
               'registrar_ajuste'],
  'activo': True,
  'alcance': 'todas',
  'creada': '2024-01-12',
  'desactivada': None},
 {'codigo': 'ROL-05',
  'nombre': 'Administrador',
  'descripcion': 'Gestiona el acceso y los catálogos, y es el único que '
                 'consulta la auditoría completa.',
  'permisos': ['gestionar_usuario',
               'gestionar_catalogo',
               'ver_auditoria',
               'configurar_periodo',
               'ver_informes'],
  'activo': True,
  'alcance': 'todas',
  'creada': '2024-01-12',
  'desactivada': None},
 {'codigo': 'ROL-06',
  'nombre': 'Usuario de consulta',
  'descripcion': 'Solo lectura de informes del ámbito que se le autorice. '
                 'Pensado para jefaturas externas.',
  'permisos': ['ver_informes'],
  'activo': False,
  'alcance': 'varias',
  'creada': '2024-05-20',
  'desactivada': '2026-07-31'}]

USUARIOS = [{'codigo': 'USR-01',
  'nombre': 'Marcela Ríos',
  'correo': 'marcela.rios@ejemplo.cl',
  'cargo': 'Encargado territorial',
  'delegacion': 'DEL-01',
  'autorizadas': ['DEL-01'],
  'activo': True,
  'rol': 'Funcionario',
  'otros_roles': [],
  'creada': '2024-01-12',
  'desactivada': None},
 {'codigo': 'USR-02',
  'nombre': 'Jorge Salinas',
  'correo': 'jorge.salinas@ejemplo.cl',
  'cargo': 'Inspector municipal',
  'delegacion': 'DEL-01',
  'autorizadas': ['DEL-01'],
  'activo': True,
  'rol': 'Funcionario',
  'otros_roles': [],
  'creada': '2024-01-12',
  'desactivada': None},
 {'codigo': 'USR-03',
  'nombre': 'Pablo Fuentes',
  'correo': 'pablo.fuentes@ejemplo.cl',
  'cargo': 'Coordinador de delegación',
  'delegacion': 'DEL-01',
  'autorizadas': ['DEL-01'],
  'activo': True,
  'rol': 'Verificador',
  'otros_roles': ['Delegado o jefatura'],
  'creada': '2024-01-12',
  'desactivada': None},
 {'codigo': 'USR-04',
  'nombre': 'Camila Otárola',
  'correo': 'camila.otarola@ejemplo.cl',
  'cargo': 'Asistente social',
  'delegacion': 'DEL-01',
  'autorizadas': ['DEL-01'],
  'activo': True,
  'rol': 'Funcionario',
  'otros_roles': [],
  'creada': '2024-03-03',
  'desactivada': None},
 {'codigo': 'USR-05',
  'nombre': 'Héctor Pizarro',
  'correo': 'hector.pizarro@ejemplo.cl',
  'cargo': 'Inspector municipal',
  'delegacion': 'DEL-02',
  'autorizadas': ['DEL-02'],
  'activo': True,
  'rol': 'Funcionario',
  'otros_roles': [],
  'creada': '2024-03-03',
  'desactivada': None},
 {'codigo': 'USR-06',
  'nombre': 'Ana Villalobos',
  'correo': 'ana.villalobos@ejemplo.cl',
  'cargo': 'Coordinador de delegación',
  'delegacion': 'DEL-02',
  'autorizadas': ['DEL-02'],
  'activo': True,
  'rol': 'Verificador',
  'otros_roles': ['Delegado o jefatura'],
  'creada': '2024-03-03',
  'desactivada': None},
 {'codigo': 'USR-07',
  'nombre': 'Rodrigo Tapia',
  'correo': 'rodrigo.tapia@ejemplo.cl',
  'cargo': 'Encargado territorial',
  'delegacion': 'DEL-02',
  'autorizadas': ['DEL-02'],
  'activo': True,
  'rol': 'Funcionario',
  'otros_roles': [],
  'creada': '2024-05-20',
  'desactivada': None},
 {'codigo': 'USR-08',
  'nombre': 'Lorena Bugueño',
  'correo': 'lorena.bugueno@ejemplo.cl',
  'cargo': 'Asistente social',
  'delegacion': 'DEL-03',
  'autorizadas': ['DEL-03'],
  'activo': False,
  'rol': 'Funcionario',
  'otros_roles': [],
  'creada': '2024-05-20',
  'desactivada': '2026-07-01'},
 {'codigo': 'USR-09',
  'nombre': 'Ignacio Peralta',
  'correo': 'ignacio.peralta@ejemplo.cl',
  'cargo': 'Inspector municipal',
  'delegacion': 'DEL-03',
  'autorizadas': ['DEL-03'],
  'activo': True,
  'rol': 'Funcionario',
  'otros_roles': [],
  'creada': '2024-06-11',
  'desactivada': None},
 {'codigo': 'USR-10',
  'nombre': 'Paulina Mondaca',
  'correo': 'paulina.mondaca@ejemplo.cl',
  'cargo': 'Asistente social',
  'delegacion': 'DEL-07',
  'autorizadas': ['DEL-07'],
  'activo': True,
  'rol': 'Funcionario',
  'otros_roles': [],
  'creada': '2024-06-11',
  'desactivada': None},
 {'codigo': 'USR-11',
  'nombre': 'Tomás Carvajal',
  'correo': 'tomas.carvajal@ejemplo.cl',
  'cargo': 'Encargado territorial',
  'delegacion': 'DEL-11',
  'autorizadas': ['DEL-11'],
  'activo': True,
  'rol': 'Funcionario',
  'otros_roles': [],
  'creada': '2024-07-08',
  'desactivada': None},
 {'codigo': 'USR-12',
  'nombre': 'Rosa Ahumada',
  'correo': 'rosa.ahumada@ejemplo.cl',
  'cargo': 'Coordinador de delegación',
  'delegacion': 'DEL-11',
  'autorizadas': ['DEL-11'],
  'activo': True,
  'rol': 'Verificador',
  'otros_roles': ['Delegado o jefatura'],
  'creada': '2024-07-08',
  'desactivada': None},
 {'codigo': 'USR-13',
  'nombre': 'Valentina Cortés',
  'correo': 'valentina.cortes@ejemplo.cl',
  'cargo': 'Coordinador del sistema',
  'delegacion': 'DEL-01',
  'autorizadas': ['DEL-01', 'DEL-02', 'DEL-03', 'DEL-07', 'DEL-11'],
  'activo': True,
  'rol': 'Coordinador del sistema',
  'otros_roles': [],
  'creada': '2024-01-12',
  'desactivada': None},
 {'codigo': 'USR-14',
  'nombre': 'Felipe Araya',
  'correo': 'felipe.araya@ejemplo.cl',
  'cargo': 'Administrador del sistema',
  'delegacion': 'DEL-01',
  'autorizadas': ['DEL-01', 'DEL-02', 'DEL-07', 'DEL-11'],
  'activo': True,
  'rol': 'Administrador',
  'otros_roles': [],
  'creada': '2024-01-12',
  'desactivada': None},
 # El rol «Delegado o jefatura» es el único con el permiso de reasignar
 # compromisos, y hasta ahora ningún usuario de demostración lo tenía como rol
 # principal: la reasignación del caso AGE-06 quedaba definida en la tabla de
 # permisos y sin nadie que pudiera ejecutarla. Esta cuenta cierra ese hueco.
 {'codigo': 'USR-15',
  'nombre': 'Soledad Guerrero',
  'correo': 'soledad.guerrero@ejemplo.cl',
  'cargo': 'Delegada municipal',
  'delegacion': 'DEL-01',
  'autorizadas': ['DEL-01', 'DEL-02'],
  'activo': True,
  'rol': 'Delegado o jefatura',
  'otros_roles': [],
  'creada': '2024-02-19',
  'desactivada': None}]

ITEMS = [{'codigo': 'ITM-01',
  'nombre': 'Atenciones de público realizadas',
  'descripcion': 'Atenciones presenciales en la delegación, registradas con '
                 'su tipo y subatención.',
  'area': 'Territorial',
  'unidad': 'Cantidad',
  'meta': 120,
  'ponderador': 20,
  'activo': True,
  'creada': '2024-01-12',
  'desactivada': None},
 {'codigo': 'ITM-02',
  'nombre': 'Visitas en terreno',
  'descripcion': 'Salidas a terreno con evidencia fotográfica o acta '
                 'firmada.',
  'area': 'Territorial',
  'unidad': 'Cantidad',
  'meta': 40,
  'ponderador': 15,
  'activo': True,
  'creada': '2024-01-12',
  'desactivada': None},
 {'codigo': 'ITM-03',
  'nombre': 'Casos sociales con seguimiento',
  'descripcion': 'Casos con al menos dos intervenciones registradas dentro '
                 'del período.',
  'area': 'Social',
  'unidad': 'Cantidad',
  'meta': 25,
  'ponderador': 20,
  'activo': True,
  'creada': '2024-01-12',
  'desactivada': None},
 {'codigo': 'ITM-04',
  'nombre': 'Fiscalizaciones realizadas',
  'descripcion': 'Fiscalizaciones de ferias, patentes y ocupación de bien '
                 'nacional de uso público.',
  'area': 'Inspección',
  'unidad': 'Cantidad',
  'meta': 60,
  'ponderador': 15,
  'activo': True,
  'creada': '2024-01-12',
  'desactivada': None},
 {'codigo': 'ITM-05',
  'nombre': 'Mesas de trabajo con la comunidad',
  'descripcion': 'Reuniones con juntas de vecinos u organizaciones, con '
                 'acta.',
  'area': 'Territorial',
  'unidad': 'Cantidad',
  'meta': 8,
  'ponderador': 10,
  'activo': True,
  'creada': '2024-03-03',
  'desactivada': None},
 {'codigo': 'ITM-06',
  'nombre': 'Compromisos cerrados en plazo',
  'descripcion': 'Proporción de compromisos que se cierran antes de su fecha '
                 'de vencimiento.',
  'area': 'Transversal',
  'unidad': 'Porcentaje',
  'meta': 85,
  'ponderador': 10,
  'activo': True,
  'creada': '2024-03-03',
  'desactivada': None},
 {'codigo': 'ITM-07',
  'nombre': 'Evidencias aprobadas al primer intento',
  'descripcion': 'Mide la calidad del respaldo que se adjunta, no la '
                 'cantidad.',
  'area': 'Transversal',
  'unidad': 'Porcentaje',
  'meta': 90,
  'ponderador': 5,
  'activo': True,
  'creada': '2024-05-20',
  'desactivada': None},
 {'codigo': 'ITM-08',
  'nombre': 'Catastros actualizados',
  'descripcion': 'Actualización de catastros de luminarias, veredas y '
                 'microbasurales.',
  'area': 'Territorial',
  'unidad': 'Cantidad',
  'meta': 12,
  'ponderador': 5,
  'activo': True,
  'creada': '2024-05-20',
  'desactivada': None},
 {'codigo': 'ITM-09',
  'nombre': 'Operativos de invierno',
  'descripcion': 'Se mide solo en los períodos de abril a septiembre.',
  'area': 'Territorial',
  'unidad': 'Cantidad',
  'meta': 4,
  'ponderador': 0,
  'activo': False,
  'creada': '2024-06-11',
  'desactivada': '2026-09-09'},
 {'codigo': 'ITM-10',
  'nombre': 'Horas de capacitación',
  'descripcion': 'Propuesto para el período siguiente; todavía sin '
                 'ponderador asignado.',
  'area': 'Transversal',
  'unidad': 'Horas',
  'meta': 16,
  'ponderador': 0,
  'activo': False,
  'creada': '2026-09-01',
  'desactivada': '2026-09-01'}]

TIPOS = [{'codigo': 'TAT-01',
  'nombre': 'Asistencia social',
  'descripcion': 'Ayudas sociales directas: alimentos, pañales, medicamentos '
                 'y apoyo en emergencias.',
  'area': 'Social',
  'activo': True,
  'creada': '2024-01-12',
  'desactivada': None},
 {'codigo': 'TAT-02',
  'nombre': 'Vivienda y subsidios',
  'descripcion': 'Orientación sobre postulaciones, comités de vivienda y '
                 'regularización.',
  'area': 'Social',
  'activo': True,
  'creada': '2024-01-12',
  'desactivada': None},
 {'codigo': 'TAT-03',
  'nombre': 'Servicios básicos',
  'descripcion': 'Reclamos y solicitudes de luminarias, agua, alcantarillado '
                 'y veredas.',
  'area': 'Territorial',
  'activo': True,
  'creada': '2024-01-12',
  'desactivada': None},
 {'codigo': 'TAT-04',
  'nombre': 'Trámites municipales',
  'descripcion': 'Certificados, permisos, patentes y derivaciones a otras '
                 'unidades.',
  'area': 'Transversal',
  'activo': True,
  'creada': '2024-01-12',
  'desactivada': None},
 {'codigo': 'TAT-05',
  'nombre': 'Seguridad y convivencia',
  'descripcion': 'Denuncias vecinales, mediación y coordinación con '
                 'seguridad ciudadana.',
  'area': 'Territorial',
  'activo': True,
  'creada': '2024-03-03',
  'desactivada': None},
 {'codigo': 'TAT-06',
  'nombre': 'Salud y adulto mayor',
  'descripcion': 'Derivación a consultorios, programas del adulto mayor y '
                 'ayudas técnicas.',
  'area': 'Social',
  'activo': True,
  'creada': '2024-03-03',
  'desactivada': None},
 {'codigo': 'TAT-07',
  'nombre': 'Medioambiente',
  'descripcion': 'Microbasurales, tenencia responsable de mascotas y '
                 'arbolado urbano.',
  'area': 'Territorial',
  'activo': True,
  'creada': '2024-05-20',
  'desactivada': None},
 {'codigo': 'TAT-08',
  'nombre': 'Operativo de invierno',
  'descripcion': 'Campaña estacional. Se reactiva cada abril junto con el '
                 'ítem correspondiente.',
  'area': 'Social',
  'activo': False,
  'creada': '2024-06-11',
  'desactivada': '2026-09-09'}]

SUBATENCIONES = [{'codigo': 'SAT-01',
  'nombre': 'Entrega de alimentos',
  'descripcion': 'Caja de mercadería de emergencia. Requiere informe social '
                 'vigente.',
  'documento': True,
  'activo': True,
  'tipo': 'TAT-01',
  'creada': '2024-01-12',
  'desactivada': None},
 {'codigo': 'SAT-02',
  'nombre': 'Ayuda en medicamentos',
  'descripcion': 'Compra o reembolso de medicamentos no cubiertos. Requiere '
                 'receta.',
  'documento': True,
  'activo': True,
  'tipo': 'TAT-01',
  'creada': '2024-01-12',
  'desactivada': None},
 {'codigo': 'SAT-03',
  'nombre': 'Apoyo en emergencia habitacional',
  'descripcion': 'Materiales de construcción tras siniestro, con visita '
                 'domiciliaria previa.',
  'documento': True,
  'activo': True,
  'tipo': 'TAT-01',
  'creada': '2024-01-12',
  'desactivada': None},
 {'codigo': 'SAT-04',
  'nombre': 'Entrega de pañales',
  'descripcion': 'Para adultos mayores y personas en situación de '
                 'dependencia.',
  'documento': False,
  'activo': True,
  'tipo': 'TAT-01',
  'creada': '2024-03-03',
  'desactivada': None},
 {'codigo': 'SAT-05',
  'nombre': 'Postulación a subsidio',
  'descripcion': 'Orientación y revisión de antecedentes para postular.',
  'documento': True,
  'activo': True,
  'tipo': 'TAT-02',
  'creada': '2024-01-12',
  'desactivada': None},
 {'codigo': 'SAT-06',
  'nombre': 'Comité de vivienda',
  'descripcion': 'Apoyo a la organización y seguimiento de comités del '
                 'sector.',
  'documento': False,
  'activo': True,
  'tipo': 'TAT-02',
  'creada': '2024-01-12',
  'desactivada': None},
 {'codigo': 'SAT-07',
  'nombre': 'Regularización de propiedad',
  'descripcion': 'Derivación al programa de saneamiento de títulos.',
  'documento': True,
  'activo': True,
  'tipo': 'TAT-02',
  'creada': '2024-05-20',
  'desactivada': None},
 {'codigo': 'SAT-08',
  'nombre': 'Reposición de luminarias',
  'descripcion': 'Se levanta con la dirección exacta y el número de poste si '
                 'existe.',
  'documento': False,
  'activo': True,
  'tipo': 'TAT-03',
  'creada': '2024-01-12',
  'desactivada': None},
 {'codigo': 'SAT-09',
  'nombre': 'Reparación de veredas',
  'descripcion': 'Requiere fotografía del tramo y su medida aproximada.',
  'documento': False,
  'activo': True,
  'tipo': 'TAT-03',
  'creada': '2024-01-12',
  'desactivada': None},
 {'codigo': 'SAT-10',
  'nombre': 'Agua y alcantarillado',
  'descripcion': 'Se deriva a la empresa sanitaria y se deja el número de '
                 'caso.',
  'documento': False,
  'activo': True,
  'tipo': 'TAT-03',
  'creada': '2024-03-03',
  'desactivada': None},
 {'codigo': 'SAT-11',
  'nombre': 'Certificado de residencia',
  'descripcion': 'La junta de vecinos lo emite; la delegación lo timbra y '
                 'registra.',
  'documento': True,
  'activo': True,
  'tipo': 'TAT-04',
  'creada': '2024-01-12',
  'desactivada': None},
 {'codigo': 'SAT-12',
  'nombre': 'Permiso de circulación',
  'descripcion': 'Orientación sobre el trámite y derivación a la tesorería '
                 'municipal.',
  'documento': True,
  'activo': True,
  'tipo': 'TAT-04',
  'creada': '2024-01-12',
  'desactivada': None},
 {'codigo': 'SAT-13',
  'nombre': 'Patente comercial',
  'descripcion': 'Orientación a microempresarios del sector.',
  'documento': True,
  'activo': True,
  'tipo': 'TAT-04',
  'creada': '2024-01-12',
  'desactivada': None},
 {'codigo': 'SAT-14',
  'nombre': 'Derivación a otra unidad',
  'descripcion': 'Cuando el requerimiento no se resuelve en la delegación.',
  'documento': False,
  'activo': True,
  'tipo': 'TAT-04',
  'creada': '2024-05-20',
  'desactivada': None},
 {'codigo': 'SAT-15',
  'nombre': 'Denuncia vecinal',
  'descripcion': 'Ruidos molestos, sitios eriazos y ocupación indebida.',
  'documento': False,
  'activo': True,
  'tipo': 'TAT-05',
  'creada': '2024-03-03',
  'desactivada': None},
 {'codigo': 'SAT-16',
  'nombre': 'Mediación vecinal',
  'descripcion': 'Conflictos entre vecinos. Termina en acta de acuerdo.',
  'documento': True,
  'activo': True,
  'tipo': 'TAT-05',
  'creada': '2024-03-03',
  'desactivada': None},
 {'codigo': 'SAT-17',
  'nombre': 'Coordinación con seguridad',
  'descripcion': 'Solicitudes de ronda preventiva o cámaras.',
  'documento': False,
  'activo': True,
  'tipo': 'TAT-05',
  'creada': '2024-05-20',
  'desactivada': None},
 {'codigo': 'SAT-18',
  'nombre': 'Derivación a consultorio',
  'descripcion': 'Agenda de horas y orientación sobre el centro que '
                 'corresponde.',
  'documento': False,
  'activo': True,
  'tipo': 'TAT-06',
  'creada': '2024-03-03',
  'desactivada': None},
 {'codigo': 'SAT-19',
  'nombre': 'Programa del adulto mayor',
  'descripcion': 'Inscripción en talleres y actividades del sector.',
  'documento': False,
  'activo': True,
  'tipo': 'TAT-06',
  'creada': '2024-03-03',
  'desactivada': None},
 {'codigo': 'SAT-20',
  'nombre': 'Entrega de ayuda técnica',
  'descripcion': 'Sillas de ruedas, bastones y andadores. Requiere informe.',
  'documento': True,
  'activo': True,
  'tipo': 'TAT-06',
  'creada': '2024-05-20',
  'desactivada': None},
 {'codigo': 'SAT-21',
  'nombre': 'Retiro de microbasural',
  'descripcion': 'Se coordina con aseo y ornato; queda con fecha '
                 'comprometida.',
  'documento': False,
  'activo': True,
  'tipo': 'TAT-07',
  'creada': '2024-05-20',
  'desactivada': None},
 {'codigo': 'SAT-22',
  'nombre': 'Tenencia responsable',
  'descripcion': 'Esterilización, chip y denuncias por maltrato animal.',
  'documento': False,
  'activo': True,
  'tipo': 'TAT-07',
  'creada': '2024-05-20',
  'desactivada': None},
 {'codigo': 'SAT-23',
  'nombre': 'Entrega de frazadas',
  'descripcion': 'Campaña de invierno. Se reactiva junto con su tipo.',
  'documento': False,
  'activo': False,
  'tipo': 'TAT-08',
  'creada': '2024-06-11',
  'desactivada': '2026-09-09'},
 {'codigo': 'SAT-24',
  'nombre': 'Reparación de techumbre',
  'descripcion': 'Materiales por filtraciones. Campaña de invierno.',
  'documento': True,
  'activo': False,
  'tipo': 'TAT-08',
  'creada': '2024-06-11',
  'desactivada': '2026-09-09'}]

PERSONAS = [{'rut': '15834276-6',
  'nombre': 'Rosa Elena Vega',
  'telefono': '9 6543 2101',
  'territorio': 'Unidad vecinal 1 · El Mirador'},
 {'rut': '9876543-3',
  'nombre': 'Manuel Ossandón',
  'telefono': '9 7210 4432',
  'territorio': 'Unidad vecinal 3 · San Juan'},
 {'rut': '18245901-1',
  'nombre': 'Fabiola Araya',
  'telefono': '9 5588 9012',
  'territorio': 'Unidad vecinal 2 · Los Aromos'},
 {'rut': '12456789-0',
  'nombre': 'Nelson Cortés',
  'telefono': '',
  'territorio': 'Unidad vecinal 5 · El Milagro Alto'},
 {'rut': '20114558-9',
  'nombre': 'Javiera Muñoz',
  'telefono': '9 3344 7788',
  'territorio': 'Unidad vecinal 4 · Villa Esperanza'}]

ATENCIONES = [('SAT-01',
  'marcela.rios@ejemplo.cl',
  'DEL-01',
  'Solicita caja de mercadería por pérdida de empleo del jefe de hogar. Se '
  'entrega con informe social vigente y se agenda seguimiento en 30 días.',
  'Informe social 2026-0412'),
 ('SAT-21',
  'jorge.salinas@ejemplo.cl',
  'DEL-01',
  'Denuncia acumulación de residuos en el sitio eriazo de la esquina. Se '
  'coordina retiro con aseo y se notificará al propietario del terreno.',
  ''),
 ('SAT-05',
  'camila.otarola@ejemplo.cl',
  'DEL-01',
  'Postula al subsidio de arriendo con su grupo familiar. Se revisa la '
  'documentación, se completa la ficha y queda en evaluación.',
  'Ficha de postulación 2026-0931'),
 ('SAT-04',
  'hector.pizarro@ejemplo.cl',
  'DEL-02',
  'Requiere pañales de adulto para su madre postrada. Se entrega el paquete '
  'mensual y queda registrada la recepción conforme.',
  ''),
 ('SAT-11',
  'tomas.carvajal@ejemplo.cl',
  'DEL-11',
  'Pide certificado de residencia para un trámite bancario. Se emite en el '
  'momento y se le explica su vigencia de 60 días.',
  'Certificado de residencia 2026-2240'),
 ('SAT-09',
  'paulina.mondaca@ejemplo.cl',
  'DEL-07',
  'Reporta una vereda levantada frente a su domicilio, con riesgo de caída. '
  'Se ingresa a la programación de reparaciones del sector.',
  '')]


# --- Cargos del catálogo -------------------------------------------------
# Son los de la maqueta. El cargo decide con qué ítems y metas se mide a una
# persona; el rol decide qué pantallas puede usar. Son cosas distintas.
CARGOS = [
    ("CAR-01", "Encargado territorial",
     "Coordina el trabajo en terreno del sector y acompaña a las juntas de vecinos."),
    ("CAR-02", "Inspector municipal",
     "Fiscaliza en terreno y levanta las actas de las denuncias recibidas."),
    ("CAR-03", "Asistente social",
     "Atiende los casos sociales de la delegación y gestiona las ayudas directas."),
    ("CAR-04", "Coordinador de delegación",
     "Conduce la delegación, revisa evidencias y responde por su resultado."),
    ("CAR-05", "Coordinador del sistema",
     "Define períodos, metas y ponderadores para todas las delegaciones."),
    ("CAR-06", "Administrador del sistema",
     "Gestiona el acceso y los catálogos; no se mide con metas de terreno."),
]

# --- Período de demostración ---------------------------------------------
# Abierto y en curso, para que el tablero y las actividades tengan dónde
# sumar. Las fechas se calculan alrededor de hoy al cargar.
PERIODO = ("PER-01", "Período de demostración")

# cargo, ítem, meta, ponderador · cada cargo suma 100 %
METAS = [
    ("CAR-01", "ITM-01", 120, 35),
    ("CAR-01", "ITM-02", 40, 25),
    ("CAR-01", "ITM-05", 8, 20),
    ("CAR-01", "ITM-06", 85, 20),

    ("CAR-02", "ITM-04", 60, 50),
    ("CAR-02", "ITM-02", 40, 30),
    ("CAR-02", "ITM-06", 85, 20),

    ("CAR-03", "ITM-03", 25, 45),
    ("CAR-03", "ITM-01", 120, 30),
    ("CAR-03", "ITM-07", 90, 25),

    ("CAR-04", "ITM-06", 85, 40),
    ("CAR-04", "ITM-07", 90, 35),
    ("CAR-04", "ITM-08", 12, 25),
]

# --- Actividades ya registradas ------------------------------------------
# Correo → qué fracción de cada una de sus metas tiene ya aprobada. Con los
# ponderadores sumando 100 %, el avance resultante es esa fracción en
# porcentaje: 0,62 da un 62 %. Las tres zonas del semáforo quedan
# representadas, para que la pantalla de resultados muestre verde, ámbar y
# rojo sin tener que inventar datos en la demostración.
AVANCE_DEMO = {
    "marcela.rios@ejemplo.cl": 0.62,
    "jorge.salinas@ejemplo.cl": 0.45,
    "camila.otarola@ejemplo.cl": 0.30,
    "pablo.fuentes@ejemplo.cl": 0.55,
    "hector.pizarro@ejemplo.cl": 0.40,
    "ana.villalobos@ejemplo.cl": 0.48,
    "rodrigo.tapia@ejemplo.cl": 0.70,
    "ignacio.peralta@ejemplo.cl": 0.58,
    "paulina.mondaca@ejemplo.cl": 0.52,
    "tomas.carvajal@ejemplo.cl": 0.35,
    "rosa.ahumada@ejemplo.cl": 0.44,
}

# Quién valida en cada delegación. Es el verificador de esa delegación, que
# es quien de verdad podría haber aprobado estas evidencias.
VERIFICADOR_POR_DELEGACION = {
    "DEL-01": "pablo.fuentes@ejemplo.cl",
    "DEL-02": "ana.villalobos@ejemplo.cl",
    "DEL-11": "rosa.ahumada@ejemplo.cl",
}
VERIFICADOR_POR_OMISION = "valentina.cortes@ejemplo.cl"

# Compromisos de la agenda.
#
# DEL-01 queda con la forma exacta del lote CAL-C —8 realizados, 1 pendiente y
# 1 en proceso, o sea 80 % realizado y 20 % no realizado— más un anulado que
# **no** entra en esos diez, porque un compromiso dado de baja sale del
# denominador en vez de contar como incumplido.
#
# «vence_en» son días desde hoy: negativo es un vencimiento ya pasado.
# «cerro_tarde» son los días de atraso con que se cerró.
#
# Los solicitantes son organizaciones vecinales inventadas y los territorios
# los mismos de las delegaciones. No aparece ninguna persona identificable.
COMPROMISOS_DEMO = [
    # --- DEL-01: los ocho realizados ---------------------------------------
    {"delegacion": "DEL-01", "responsable": "marcela.rios@ejemplo.cl",
     "solicitante": "Junta de vecinos Las Acacias", "item": "ITM-01",
     "territorio": "Unidad vecinal 1 · El Mirador", "vence_en": -34,
     "descripcion": "Coordinar el retiro de escombros acumulados en la plaza "
                    "del sector y dejar constancia del retiro.",
     "estado": Compromiso.Estado.REALIZADO,
     "observacion": "Se coordinó con aseo y se retiró en la fecha acordada."},
    {"delegacion": "DEL-01", "responsable": "marcela.rios@ejemplo.cl",
     "solicitante": "Comité de adelanto Vista Hermosa", "item": "ITM-01",
     "territorio": "Unidad vecinal 1 · El Mirador", "vence_en": -27,
     "descripcion": "Gestionar la reposición de tres luminarias apagadas en "
                    "el pasaje principal del sector.",
     "estado": Compromiso.Estado.REALIZADO},
    {"delegacion": "DEL-01", "responsable": "jorge.salinas@ejemplo.cl",
     "solicitante": "Club deportivo El Olivo", "item": "ITM-02",
     "territorio": "Unidad vecinal 1 · El Mirador", "vence_en": -21,
     "descripcion": "Revisar el estado de la multicancha y levantar el "
                    "informe con lo que requiere reparación.",
     "estado": Compromiso.Estado.REALIZADO, "cerro_tarde": 4,
     "observacion": "Se cerró con atraso: la visita se reprogramó dos veces."},
    {"delegacion": "DEL-01", "responsable": "jorge.salinas@ejemplo.cl",
     "solicitante": "Junta de vecinos Los Nogales", "item": "ITM-02",
     "territorio": "Unidad vecinal 1 · El Mirador", "vence_en": -18,
     "descripcion": "Fiscalizar la ocupación de la vereda frente al "
                    "comercio del sector y notificar lo que corresponda.",
     "estado": Compromiso.Estado.REALIZADO},
    {"delegacion": "DEL-01", "responsable": "camila.otarola@ejemplo.cl",
     "solicitante": "Centro de madres Flor de Añañuca", "item": "ITM-03",
     "territorio": "Unidad vecinal 1 · El Mirador", "vence_en": -14,
     "descripcion": "Orientar a la organización en la postulación al fondo "
                    "de desarrollo vecinal y entregar el listado de "
                    "requisitos.",
     "estado": Compromiso.Estado.REALIZADO},
    {"delegacion": "DEL-01", "responsable": "camila.otarola@ejemplo.cl",
     "solicitante": "Junta de vecinos Las Acacias", "item": "ITM-03",
     "territorio": "Unidad vecinal 1 · El Mirador", "vence_en": -11,
     "descripcion": "Derivar a la unidad social los casos levantados en la "
                    "última jornada de atención en terreno.",
     "estado": Compromiso.Estado.REALIZADO},
    {"delegacion": "DEL-01", "responsable": "marcela.rios@ejemplo.cl",
     "solicitante": "Comité de agua potable rural El Molle", "item": "ITM-01",
     "territorio": "Unidad vecinal 1 · El Mirador", "vence_en": -7,
     "descripcion": "Entregar el informe de la reunión sostenida con el "
                    "comité y las gestiones comprometidas en ella.",
     "estado": Compromiso.Estado.REALIZADO},
    # Este queda realizado pero **sin validar**: es la distinción del caso
    # AGE-05 entre cerrado y puntuado, a la vista en la demostración.
    {"delegacion": "DEL-01", "responsable": "jorge.salinas@ejemplo.cl",
     "solicitante": "Junta de vecinos Los Nogales", "item": "ITM-02",
     "territorio": "Unidad vecinal 1 · El Mirador", "vence_en": -3,
     "descripcion": "Catastrar los puntos de acopio irregular detectados en "
                    "el recorrido del sector alto.",
     "estado": Compromiso.Estado.REALIZADO, "validado": False,
     "observacion": "Cerrado por el responsable; espera validación."},

    # --- DEL-01: uno pendiente y uno en proceso ----------------------------
    {"delegacion": "DEL-01", "responsable": "marcela.rios@ejemplo.cl",
     "solicitante": "Club deportivo El Olivo", "item": "ITM-01",
     "territorio": "Unidad vecinal 1 · El Mirador", "vence_en": -5,
     "descripcion": "Coordinar con la unidad de áreas verdes la poda de los "
                    "árboles que obstruyen el alumbrado del sector.",
     "estado": Compromiso.Estado.PENDIENTE,
     "observacion": "A la espera de la programación de áreas verdes."},
    {"delegacion": "DEL-01", "responsable": "camila.otarola@ejemplo.cl",
     "solicitante": "Junta de vecinos Las Acacias", "item": "ITM-03",
     "territorio": "Unidad vecinal 1 · El Mirador", "vence_en": 6,
     "descripcion": "Acompañar a la directiva en la preparación de la cuenta "
                    "pública anual de la organización.",
     "estado": Compromiso.Estado.EN_PROCESO,
     "apoyo": "Equipo social de la delegación"},

    # --- DEL-01: el anulado, que sale del denominador ----------------------
    {"delegacion": "DEL-01", "responsable": "jorge.salinas@ejemplo.cl",
     "solicitante": "Comité de adelanto Vista Hermosa",
     "territorio": "Unidad vecinal 1 · El Mirador", "vence_en": -9,
     "descripcion": "Fiscalizar el cierre de un sitio eriazo en el sector "
                    "norte de la unidad vecinal.",
     "estado": Compromiso.Estado.ANULADO,
     "observacion": "Se anula: el sitio no pertenece al territorio de esta "
                    "delegación y se derivó a la unidad competente."},

    # --- DEL-02 ------------------------------------------------------------
    {"delegacion": "DEL-02", "responsable": "hector.pizarro@ejemplo.cl",
     "solicitante": "Junta de vecinos Villa El Sauce", "item": "ITM-01",
     "territorio": "Unidad vecinal 3 · San Juan", "vence_en": -16,
     "descripcion": "Gestionar la reparación del cierre perimetral de la "
                    "sede vecinal y verificar su ejecución.",
     "estado": Compromiso.Estado.REALIZADO},
    {"delegacion": "DEL-02", "responsable": "rodrigo.tapia@ejemplo.cl",
     "solicitante": "Comité de seguridad Los Aromos", "item": "ITM-02",
     "territorio": "Unidad vecinal 3 · San Juan", "vence_en": -12,
     "descripcion": "Levantar el catastro de luminarias en mal estado del "
                    "sector y remitirlo a la unidad correspondiente.",
     "estado": Compromiso.Estado.REALIZADO, "cerro_tarde": 2},
    {"delegacion": "DEL-02", "responsable": "rodrigo.tapia@ejemplo.cl",
     "solicitante": "Junta de vecinos Villa El Sauce", "item": "ITM-01",
     "territorio": "Unidad vecinal 3 · San Juan", "vence_en": -2,
     "descripcion": "Coordinar la visita de la unidad de tránsito para "
                    "evaluar la demarcación del cruce escolar.",
     "estado": Compromiso.Estado.EN_PROCESO},
    {"delegacion": "DEL-02", "responsable": "hector.pizarro@ejemplo.cl",
     "solicitante": "Club de huasos El Peumo",
     "territorio": "Unidad vecinal 3 · San Juan", "vence_en": 9,
     "descripcion": "Entregar la orientación sobre el permiso municipal "
                    "para la actividad programada por la organización.",
     "estado": Compromiso.Estado.INGRESADO},

    # --- DEL-11 ------------------------------------------------------------
    {"delegacion": "DEL-11", "responsable": "tomas.carvajal@ejemplo.cl",
     "solicitante": "Junta de vecinos El Milagro Alto", "item": "ITM-01",
     "territorio": "Unidad vecinal 5 · El Milagro Alto", "vence_en": -20,
     "descripcion": "Coordinar el mejoramiento del acceso peatonal al sector "
                    "alto y verificar el término de la obra.",
     "estado": Compromiso.Estado.REALIZADO},
    {"delegacion": "DEL-11", "responsable": "tomas.carvajal@ejemplo.cl",
     "solicitante": "Comité de vivienda Nueva Esperanza", "item": "ITM-03",
     "territorio": "Unidad vecinal 5 · El Milagro Alto", "vence_en": -4,
     "descripcion": "Orientar al comité en la actualización de su personalidad "
                    "jurídica y entregar los formularios.",
     "estado": Compromiso.Estado.PENDIENTE,
     "observacion": "Pendiente: falta que el comité reúna la documentación."},
]

# Frases con que se arman las actividades. Genéricas a propósito: describen
# trabajo municipal corriente y no mencionan a nadie.
ACCIONES_DEMO = [
    ("Mesa de trabajo con la junta de vecinos del sector",
     "Reunión con la directiva para revisar los compromisos pendientes del "
     "sector y acordar las próximas visitas en terreno."),
    ("Recorrido de inspección por el sector asignado",
     "Recorrido por las calles del sector levantando los puntos que "
     "requieren intervención, con registro fotográfico del estado de cada uno."),
    ("Atención de requerimientos en la delegación",
     "Jornada de atención de público en la delegación, con derivación de los "
     "casos que corresponden a otras unidades municipales."),
    ("Coordinación con unidades municipales",
     "Reunión de coordinación para dar curso a los requerimientos que "
     "dependen de otras direcciones y fijar plazos de respuesta."),
    ("Seguimiento de casos del período",
     "Revisión del estado de los casos abiertos del período, con cierre de "
     "los resueltos y reprogramación de los que siguen pendientes."),
]

# Qué cargo le toca a cada usuario, por el texto que ya traía su perfil.
CARGO_POR_TEXTO = {
    "Encargado territorial": "CAR-01",
    "Inspector municipal": "CAR-02",
    "Asistente social": "CAR-03",
    "Coordinador de delegación": "CAR-04",
    "Coordinador del sistema": "CAR-05",
    "Administrador del sistema": "CAR-06",
}



def _fecha(texto):
    return date.fromisoformat(texto) if texto else None


class Command(BaseCommand):
    help = "Carga los datos ficticios de la maqueta para revisar el sistema."

    def add_arguments(self, parser):
        parser.add_argument(
            "--sin-superusuario",
            action="store_true",
            help="No crea ni actualiza el usuario administrador de revisión.",
        )
        parser.add_argument(
            "--sin-atenciones",
            action="store_true",
            help="Deja el registro de atención ciudadana vacío.",
        )

    @transaction.atomic
    def handle(self, *args, **opciones):
        delegaciones = self._delegaciones()
        roles = self._roles()
        usuarios = self._usuarios(roles, delegaciones)
        self._items()
        tipos = self._tipos()
        subatenciones = self._subatenciones(tipos)
        cargos = self._cargos()
        periodo = self._periodo()
        self._metas(periodo, cargos)
        self._asignar_cargos(cargos)
        self._regla()
        self._actividades(periodo)
        self._compromisos(periodo)

        if not opciones["sin_atenciones"]:
            self._atenciones(subatenciones, usuarios, delegaciones)

        if not opciones["sin_superusuario"]:
            self._superusuario()

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            "Datos cargados: %d delegaciones, %d roles, %d usuarios, "
            "%d ítems, %d tipos, %d subatenciones, %d atenciones, "
            "%d cargos, %d metas, %d actividades, %d evidencias y "
            "%d compromisos."
            % (Delegacion.objects.count(), Rol.objects.count(),
               PerfilUsuario.objects.count(), Item.objects.count(),
               TipoAtencion.objects.count(), SubAtencion.objects.count(),
               Atencion.objects.count(), Cargo.objects.count(),
               MetaPeriodo.objects.count(), Actividad.objects.count(),
               Evidencia.objects.count(), Compromiso.objects.count())
        ))
        self.stdout.write(
            "Para entrar: felipe.araya@ejemplo.cl (Administrador) · "
            "clave «%s»." % CLAVE_DEMO
        )
        self.stdout.write(self.style.WARNING(
            "Son cuentas y datos ficticios de demostración. No usar esta "
            "clave en una instalación real."
        ))

    # --------------------------------------------------------- organización

    def _delegaciones(self):
        creadas = {}
        for fila in DELEGACIONES:
            registro, nuevo = Delegacion.objects.update_or_create(
                codigo=fila["codigo"],
                defaults={
                    "nombre": fila["nombre"],
                    "zona": fila["zona"],
                    "direccion": fila["direccion"],
                    "comuna": fila["comuna"],
                    "telefono": fila["telefono"],
                    "horario": fila["horario"],
                    "activo": fila["activo"],
                    "desactivada": _fecha(fila["desactivada"]),
                },
            )
            self._fechar(Delegacion, registro, fila["creada"])
            creadas[fila["codigo"]] = registro
            self._informar("Delegación", registro, nuevo)
        return creadas

    def _roles(self):
        creados = {}
        for fila in ROLES:
            registro, nuevo = Rol.objects.update_or_create(
                codigo=fila["codigo"],
                defaults={
                    "nombre": fila["nombre"],
                    "descripcion": fila["descripcion"],
                    "alcance": fila["alcance"],
                    "permisos": fila["permisos"],
                    "activo": fila["activo"],
                    "desactivada": _fecha(fila["desactivada"]),
                },
            )
            self._fechar(Rol, registro, fila["creada"])
            creados[fila["nombre"]] = registro
            self._informar("Rol", registro, nuevo)
        return creados

    def _usuarios(self, roles, delegaciones):
        creados = {}
        for fila in USUARIOS:
            partes = fila["nombre"].split(" ", 1)
            cuenta, nueva = User.objects.get_or_create(
                email=fila["correo"],
                defaults={
                    "username": fila["correo"],
                    "first_name": partes[0],
                    "last_name": partes[1] if len(partes) > 1 else "",
                    "is_active": True,
                },
            )
            if nueva:
                cuenta.set_password(CLAVE_DEMO)
                cuenta.save(update_fields=["password"])

            cargo = fila["cargo"]
            if fila["otros_roles"]:
                cargo = "%s · también %s" % (cargo, ", ".join(fila["otros_roles"]).lower())

            perfil, _ = PerfilUsuario.objects.update_or_create(
                codigo=fila["codigo"],
                defaults={
                    "usuario": cuenta,
                    "cargo": cargo,
                    "rol": roles[fila["rol"]],
                    "delegacion": delegaciones[fila["delegacion"]],
                    "activo": fila["activo"],
                    "desactivada": _fecha(fila["desactivada"]),
                },
            )
            perfil.delegaciones_autorizadas.set(
                [delegaciones[c] for c in fila["autorizadas"]]
            )
            self._fechar(PerfilUsuario, perfil, fila["creada"])
            creados[fila["correo"]] = perfil
            self._informar("Usuario", perfil, nueva)
        return creados

    def _superusuario(self):
        """
        Un superusuario para revisar el administrador de Django.

        La contraseña se toma del entorno. El valor por omisión existe para
        que la revisión funcione recién clonado el repositorio; en un
        servidor se define SGR_ADMIN_PASSWORD.
        """
        usuario = os.environ.get("SGR_ADMIN_USER", "revisor")
        clave = os.environ.get("SGR_ADMIN_PASSWORD", "Sgr.Revision2026")
        correo = os.environ.get("SGR_ADMIN_EMAIL", "revisor@ejemplo.cl")

        cuenta, nueva = User.objects.get_or_create(
            username=usuario,
            defaults={"email": correo, "is_staff": True, "is_superuser": True},
        )
        cuenta.is_staff = True
        cuenta.is_superuser = True
        cuenta.set_password(clave)
        cuenta.save()
        self._informar("Superusuario", cuenta, nueva)

    # ----------------------------------------------------------- catálogos

    def _items(self):
        for fila in ITEMS:
            registro, nuevo = Item.objects.update_or_create(
                codigo=fila["codigo"],
                defaults={
                    "nombre": fila["nombre"],
                    "descripcion": fila["descripcion"],
                    "area": fila["area"],
                    "unidad": fila["unidad"],
                    "meta": fila["meta"],
                    "ponderador": fila["ponderador"],
                    "activo": fila["activo"],
                    "desactivada": _fecha(fila["desactivada"]),
                },
            )
            self._fechar(Item, registro, fila["creada"])
            self._informar("Ítem", registro, nuevo)

    def _tipos(self):
        creados = {}
        for fila in TIPOS:
            registro, nuevo = TipoAtencion.objects.update_or_create(
                codigo=fila["codigo"],
                defaults={
                    "nombre": fila["nombre"],
                    "descripcion": fila["descripcion"],
                    "area": fila["area"],
                    "activo": fila["activo"],
                    "desactivada": _fecha(fila["desactivada"]),
                },
            )
            self._fechar(TipoAtencion, registro, fila["creada"])
            creados[fila["codigo"]] = registro
            self._informar("Tipo de atención", registro, nuevo)
        return creados

    def _subatenciones(self, tipos):
        creadas = {}
        for fila in SUBATENCIONES:
            registro, nuevo = SubAtencion.objects.update_or_create(
                codigo=fila["codigo"],
                defaults={
                    "nombre": fila["nombre"],
                    "descripcion": fila["descripcion"],
                    "tipo_atencion": tipos[fila["tipo"]],
                    "documento": fila["documento"],
                    "activo": fila["activo"],
                    "desactivada": _fecha(fila["desactivada"]),
                },
            )
            self._fechar(SubAtencion, registro, fila["creada"])
            creadas[fila["codigo"]] = registro
            self._informar("Subatención", registro, nuevo)
        return creadas

    # ------------------------------------------------- atención ciudadana

    def _atenciones(self, subatenciones, usuarios, delegaciones):
        fichas = {}
        for fila in PERSONAS:
            registro, nuevo = Solicitante.objects.update_or_create(
                rut=fila["rut"],
                defaults={
                    "nombre": fila["nombre"],
                    "telefono": fila["telefono"],
                    "territorio": fila["territorio"],
                },
            )
            fichas[fila["rut"]] = registro
            self._informar("Solicitante", registro, nuevo)

        for indice, (sub, correo, deleg, detalle, documento) in enumerate(ATENCIONES):
            persona = fichas[PERSONAS[indice % len(PERSONAS)]["rut"]]
            perfil = usuarios[correo]
            _, nuevo = Atencion.objects.get_or_create(
                solicitante=persona,
                subatencion=subatenciones[sub],
                delegacion=delegaciones[deleg],
                defaults={
                    "funcionario": perfil.usuario,
                    "detalle": detalle,
                    "documento": documento,
                },
            )
            if nuevo:
                self.stdout.write(
                    "  Atención: %s — %s (creada)"
                    % (persona.nombre, subatenciones[sub].nombre)
                )

    # ------------------------------------------------- período y metas

    def _cargos(self):
        creados = {}
        for codigo, nombre, descripcion in CARGOS:
            registro, nuevo = Cargo.objects.update_or_create(
                codigo=codigo,
                defaults={"nombre": nombre, "descripcion": descripcion},
            )
            creados[codigo] = registro
            self._informar("Cargo", registro, nuevo)
        return creados

    def _periodo(self):
        """
        Un período abierto que contiene el día de hoy.

        Las fechas se calculan al cargar y no se escriben fijas: así la
        demostración siempre cae dentro del período y el avance esperado da
        un número intermedio en vez de 0 % o 100 %.
        """
        from datetime import timedelta

        from django.utils import timezone

        hoy = timezone.localdate()
        inicio = hoy - timedelta(days=45)
        termino = hoy + timedelta(days=45)
        codigo, nombre = PERIODO

        registro, nuevo = Periodo.objects.update_or_create(
            codigo=codigo,
            defaults={
                "nombre": f"{nombre} · {inicio:%b} a {termino:%b} {termino:%Y}",
                "inicio": inicio,
                "termino": termino,
                "estado": Periodo.Estado.ABIERTO,
                "observacion": (
                    "Período de demostración. Las fechas se calculan al cargar "
                    "los datos para que el día de hoy quede siempre dentro."
                ),
            },
        )
        self._informar("Período", registro, nuevo)
        return registro

    def _metas(self, periodo, cargos):
        items = {i.codigo: i for i in Item.objects.all()}
        for codigo_cargo, codigo_item, meta, ponderador in METAS:
            registro, nuevo = MetaPeriodo.objects.update_or_create(
                periodo=periodo,
                cargo=cargos[codigo_cargo],
                item=items[codigo_item],
                defaults={"meta": meta, "ponderador": ponderador},
            )
            if nuevo:
                self.stdout.write(f"  Meta: {registro} ({ponderador} %) (creada)")

    def _asignar_cargos(self, cargos):
        """Enlaza cada perfil con el cargo del catálogo que le corresponde."""
        for perfil in PerfilUsuario.objects.all():
            base = (perfil.cargo or "").split(" · ")[0].strip()
            codigo = CARGO_POR_TEXTO.get(base)
            if codigo and perfil.cargo_asignado_id != cargos[codigo].pk:
                perfil.cargo_asignado = cargos[codigo]
                perfil.save(update_fields=["cargo_asignado"])

    def _regla(self):
        """
        La regla de cálculo que propone el plan de pruebas.

        Se carga **sin aprobar** a propósito. El plan deja las reglas
        pendientes de aprobación formal (sección B3), y el sistema rotula
        como propuesta todo resultado calculado con una regla sin aprobar.
        Cargarla ya aprobada sería afirmar algo que nadie firmó.
        """
        registro, nuevo = ReglaCalculo.objects.update_or_create(
            nombre="Propuesta del plan de pruebas",
            defaults={
                "periodo": None,
                "aprobada_por": "",
                "observacion": (
                    "Valores propuestos en el plan de pruebas de la segunda "
                    "evaluación, lotes CAL-A a CAL-F. Quedan pendientes de "
                    "aprobación formal: el tope del cumplimiento, el umbral "
                    "de ítem realizado, el umbral del ámbar y la convención "
                    "de días. Mientras no se aprueben, el sistema calcula "
                    "con ellos y lo dice en pantalla."
                ),
                **PROPUESTA_DEL_PLAN,
            },
        )
        self._informar("Regla de cálculo", registro, nuevo)
        return registro

    # ------------------------------------------------- actividades de demo

    @staticmethod
    def _repartir(total, trozos):
        """Reparte un total en varios enteros positivos que lo suman exacto."""
        trozos = max(1, min(trozos, total))
        base, resto = divmod(total, trozos)
        return [base + (1 if i < resto else 0) for i in range(trozos)]

    def _actividades(self, periodo):
        """
        Actividades ya registradas, con su evidencia y su decisión.

        Sin esto el sistema se ve vacío: las pantallas funcionan pero no hay
        nada que calcular, y el resultado de todo el mundo sería 0 %. Aquí se
        siembra lo justo para que cada pantalla muestre algo real y para que
        el semáforo tenga las tres zonas representadas.

        Los códigos llevan una D —``ACT-D001``— para que se distingan a
        simple vista de lo que registre una persona durante la revisión, que
        recibe ``ACT-0001`` y siguientes.
        """
        hoy = timezone.localdate()
        hasta = min(hoy, periodo.termino)
        dias = max(1, (hasta - periodo.inicio).days)

        usuarios = {u.email: u for u in User.objects.all() if u.email}
        ahora = timezone.now()
        numero = 0
        aprobadas = pendientes = rechazadas = 0

        for correo, fraccion in AVANCE_DEMO.items():
            perfil = (
                PerfilUsuario.objects
                .select_related("usuario", "cargo_asignado", "delegacion")
                .filter(usuario__email=correo, activo=True)
                .first()
            )
            if perfil is None or perfil.cargo_asignado_id is None:
                continue

            metas = list(
                MetaPeriodo.objects
                .filter(periodo=periodo, cargo=perfil.cargo_asignado, activo=True)
                .select_related("item")
                .order_by("item__codigo")
            )
            if not metas:
                continue

            correo_verificador = VERIFICADOR_POR_DELEGACION.get(
                perfil.delegacion.codigo, VERIFICADOR_POR_OMISION,
            )
            verificador = usuarios.get(correo_verificador)

            for meta in metas:
                objetivo = max(1, round(meta.meta * fraccion))
                for cantidad in self._repartir(objetivo, 3):
                    numero += 1
                    accion, detalle = ACCIONES_DEMO[numero % len(ACCIONES_DEMO)]
                    fecha = periodo.inicio + timedelta(days=(numero * 7) % dias)

                    actividad, nueva = Actividad.objects.update_or_create(
                        codigo=f"ACT-D{numero:03d}",
                        defaults={
                            "funcionario": perfil.usuario,
                            "delegacion": perfil.delegacion,
                            "periodo": periodo,
                            "item": meta.item,
                            "fecha": fecha,
                            "cantidad": cantidad,
                            "accion": accion,
                            "detalle": detalle,
                            "contacto": "",
                            "estado": Actividad.Estado.APROBADA,
                        },
                    )
                    Evidencia.objects.update_or_create(
                        codigo=f"EVI-D{numero:03d}",
                        defaults={
                            "actividad": actividad,
                            "descripcion": "Acta de la actividad y registro de asistencia",
                            "referencia": f"ACTA-{numero:03d}/{periodo.termino:%Y}",
                            "autor": perfil.usuario,
                            "decision": Evidencia.Decision.APROBADA,
                            "verificador": verificador,
                            "decidida": ahora,
                            "motivo": "",
                        },
                    )
                    if nueva:
                        aprobadas += 1

        # Unas pocas sin decidir y una rechazada, para que la cola del
        # verificador no esté vacía y para que se vea el camino de vuelta.
        sembrar = [
            ("marcela.rios@ejemplo.cl", Actividad.Estado.PENDIENTE,
             Evidencia.Decision.PENDIENTE, ""),
            ("camila.otarola@ejemplo.cl", Actividad.Estado.PENDIENTE,
             Evidencia.Decision.PENDIENTE, ""),
            ("jorge.salinas@ejemplo.cl", Actividad.Estado.RECHAZADA,
             Evidencia.Decision.RECHAZADA,
             "El acta adjunta no indica la fecha de la actividad, así que no "
             "se puede comprobar que ocurrió dentro del período. Corrígela y "
             "vuelve a enviarla."),
        ]
        for correo, estado, decision, motivo in sembrar:
            perfil = (
                PerfilUsuario.objects
                .select_related("usuario", "cargo_asignado", "delegacion")
                .filter(usuario__email=correo, activo=True)
                .first()
            )
            if perfil is None or perfil.cargo_asignado_id is None:
                continue
            meta = (
                MetaPeriodo.objects
                .filter(periodo=periodo, cargo=perfil.cargo_asignado, activo=True)
                .select_related("item")
                .order_by("item__codigo")
                .first()
            )
            if meta is None:
                continue

            numero += 1
            accion, detalle = ACCIONES_DEMO[numero % len(ACCIONES_DEMO)]
            correo_verificador = VERIFICADOR_POR_DELEGACION.get(
                perfil.delegacion.codigo, VERIFICADOR_POR_OMISION,
            )
            actividad, nueva = Actividad.objects.update_or_create(
                codigo=f"ACT-D{numero:03d}",
                defaults={
                    "funcionario": perfil.usuario,
                    "delegacion": perfil.delegacion,
                    "periodo": periodo,
                    "item": meta.item,
                    "fecha": periodo.inicio + timedelta(days=(numero * 5) % dias),
                    "cantidad": 2,
                    "accion": accion,
                    "detalle": detalle,
                    "contacto": "",
                    "estado": estado,
                },
            )
            evidencia, _ = Evidencia.objects.update_or_create(
                codigo=f"EVI-D{numero:03d}",
                defaults={
                    "actividad": actividad,
                    "descripcion": "Acta de la actividad y registro de asistencia",
                    "referencia": f"ACTA-{numero:03d}/{periodo.termino:%Y}",
                    "autor": perfil.usuario,
                    "decision": decision,
                    "verificador": (usuarios.get(correo_verificador)
                                    if decision != Evidencia.Decision.PENDIENTE
                                    else None),
                    "decidida": (ahora if decision != Evidencia.Decision.PENDIENTE
                                 else None),
                    "motivo": motivo,
                },
            )

            # Las que quedan esperando decisión se fechan ocho días atrás.
            # No es un adorno: la alerta de «evidencia sin revisar» salta a
            # los cinco días, y con la evidencia creada recién no habría
            # forma de verla funcionar sin esperar una semana. Las otras
            # cuatro alertas sí se pueden provocar en una tarde moviendo su
            # umbral, que es como se prueban.
            if decision == Evidencia.Decision.PENDIENTE:
                Evidencia.objects.filter(pk=evidencia.pk).update(
                    creada=ahora - timedelta(days=8),
                )

            if nueva and decision == Evidencia.Decision.PENDIENTE:
                pendientes += 1
            elif nueva:
                rechazadas += 1

        if aprobadas or pendientes or rechazadas:
            self.stdout.write(
                "  Actividades: %d aprobadas, %d por validar y %d rechazadas "
                "(creadas)" % (aprobadas, pendientes, rechazadas)
            )

    # --------------------------------------------------- agenda de compromisos

    def _compromisos(self, periodo):
        """
        Compromisos de la agenda, con la forma exacta del lote CAL-C.

        La delegación DEL-01 queda con **10 compromisos vigentes: 8
        realizados, 1 pendiente y 1 en proceso**, que es el lote textual del
        plan y da un realizado del 80 % y un no realizado del 20 %. Así el
        indicador que se ve en pantalla es el mismo número que el caso CAL-03
        declara verificable, y comprobarlo es mirar.

        Se agrega además **un anulado**, que no aparece en esos diez: un
        compromiso dado de baja sale del denominador en vez de contar como
        incumplido, y el 80 % tiene que seguir siendo 80 % con él presente.

        Dos de los abiertos quedan **vencidos**, para que el atraso se vea sin
        tener que esperar a que pase el tiempo.

        Los códigos llevan una D —``CMP-D001``— para distinguirlos de lo que
        alguien ingrese durante la revisión, que recibe ``CMP-0001``.
        """
        hoy = timezone.localdate()
        usuarios = {u.email: u for u in User.objects.all() if u.email}
        items = {i.codigo: i for i in Item.objects.filter(activo=True)}
        delegaciones = {d.codigo: d for d in Delegacion.objects.all()}

        creados = 0
        numero = 0

        for fila in COMPROMISOS_DEMO:
            delegacion = delegaciones.get(fila["delegacion"])
            responsable = usuarios.get(fila["responsable"])
            if delegacion is None or responsable is None:
                continue

            numero += 1
            estado = fila["estado"]
            cerrado = estado in (Compromiso.Estado.REALIZADO,
                                 Compromiso.Estado.ANULADO)
            vence = hoy + timedelta(days=fila["vence_en"])

            # El atraso se calcula igual que lo haría el sistema al cerrar: la
            # fecha de cierre contra el vencimiento. Se siembra coherente para
            # que la demostración no muestre un atraso que no cuadra.
            if cerrado:
                cerrado_el = vence + timedelta(days=fila.get("cerro_tarde", 0))
                if cerrado_el > hoy:
                    cerrado_el = hoy
                atraso = max(0, (cerrado_el - vence).days)
            else:
                cerrado_el, atraso = None, 0

            exige = fila.get("exige_validacion", True)
            compromiso, nuevo = Compromiso.objects.update_or_create(
                codigo=f"CMP-D{numero:03d}",
                defaults={
                    "delegacion": delegacion,
                    "periodo": periodo,
                    "item": items.get(fila.get("item", "")),
                    "solicitante": fila["solicitante"],
                    "territorio": fila["territorio"],
                    "descripcion": fila["descripcion"],
                    "responsable": responsable,
                    "responsable_original": responsable,
                    "apoyo": fila.get("apoyo", ""),
                    "vencimiento": vence,
                    "estado": estado,
                    "requiere_validacion": exige,
                    # Realizado y validado es lo que hace que alimente la
                    # meta; realizado sin validar queda a la vista como lo que
                    # el caso AGE-05 distingue.
                    "validado": estado == Compromiso.Estado.REALIZADO and exige
                                and fila.get("validado", True),
                    "validado_por": (
                        usuarios.get(VERIFICADOR_POR_DELEGACION.get(
                            fila["delegacion"], VERIFICADOR_POR_OMISION))
                        if estado == Compromiso.Estado.REALIZADO
                           and fila.get("validado", True)
                        else None
                    ),
                    "validado_el": (
                        timezone.now()
                        if estado == Compromiso.Estado.REALIZADO
                           and fila.get("validado", True)
                        else None
                    ),
                    "cerrado_el": cerrado_el,
                    "dias_de_atraso": atraso,
                    "cerrado_con_atraso": atraso > 0,
                    "observacion": fila.get("observacion", ""),
                },
            )
            if nuevo:
                creados += 1
                CambioCompromiso.objects.create(
                    compromiso=compromiso,
                    tipo=CambioCompromiso.Tipo.CREACION,
                    estado_nuevo=Compromiso.Estado.INGRESADO,
                    responsable_nuevo=responsable,
                    observacion="Ingresado con vencimiento al %s."
                                % vence.strftime("%d-%m-%Y"),
                )
                if estado != Compromiso.Estado.INGRESADO:
                    CambioCompromiso.objects.create(
                        compromiso=compromiso,
                        tipo=CambioCompromiso.Tipo.ESTADO,
                        estado_anterior=Compromiso.Estado.INGRESADO,
                        estado_nuevo=estado,
                        observacion=fila.get("observacion", "")
                                    or "Avanzó en el seguimiento del período.",
                    )

        if creados:
            self.stdout.write("  Compromisos de la agenda: %d (creados)" % creados)

    # ---------------------------------------------------------------- apoyo

    def _fechar(self, modelo, registro, creada):
        """Fija la fecha de creación, que auto_now_add no deja pasar."""
        if creada:
            modelo.objects.filter(pk=registro.pk).update(creada=_fecha(creada))

    def _informar(self, etiqueta, registro, nuevo):
        accion = "creado" if nuevo else "actualizado"
        self.stdout.write(f"  {etiqueta}: {registro} ({accion})")

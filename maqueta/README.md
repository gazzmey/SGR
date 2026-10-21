# Maqueta SGR — Sistema de Gestión de Resultados

Maqueta navegable del prototipo de las delegaciones municipales de La Serena. Son páginas HTML
estáticas: se abren con doble clic o se publican en cualquier hosting. No requieren servidor,
Python ni Django.

## Cómo verla

- **Local:** abrir `index.html` en el navegador.
- **GitHub Pages:** subir el contenido de esta carpeta a la raíz del repositorio y activar Pages
  en `Settings → Pages → Deploy from a branch`, rama `main`, carpeta `/ (root)`.

## Qué contiene

88 páginas y una hoja de estilos común en `assets/estilos.css`.

| Sección | Páginas |
|---|---|
| Inicio | `index.html` |
| Organización | 3 delegaciones y 8 funcionarios, con la ficha de cada uno |
| Actividades | Listado con filtros por estado, 17 actividades y 16 evidencias |
| Agenda | 8 compromisos con su historial, filtros por estado y resumen por responsable |
| Resultados | 7 metas, resultados por persona, 3 tableros de delegación e informe |
| Error | `404.html` |

Todas las fichas de detalle están generadas, así que se puede hacer clic en cualquier registro de
cualquier listado sin encontrar enlaces rotos.

## Cómo se generó

Estas páginas **no se escribieron a mano**. Se generaron ejecutando las vistas del proyecto Django
sobre los mismos archivos JSON y renderizando las mismas plantillas. Por eso la maqueta y la
aplicación muestran exactamente los mismos datos y el mismo diseño.

Los cálculos que se ven en pantalla son los de la aplicación real: el avance cuenta las actividades
validadas y los compromisos cerrados, el cumplimiento es el avance dividido por la meta, y el
semáforo compara ese resultado con la meta esperada al día del período.

## Diferencias con la aplicación

Al ser archivos estáticos hay dos cosas que no se comportan igual:

- Los filtros por estado son páginas previamente generadas, no consultas. En la aplicación Django
  son parámetros de la URL (`?estado=validada`).
- La página `404.html` existe como archivo, pero abrir una dirección inexistente no lleva a ella
  salvo que el hosting lo haga. En la aplicación, la vista levanta `Http404` cuando el
  identificador no existe.

## Datos

Todos los datos son ficticios. Los nombres, correos, direcciones y teléfonos son inventados y no
corresponden a personas reales.

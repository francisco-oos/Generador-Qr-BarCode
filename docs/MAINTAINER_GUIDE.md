# Guía de mantenimiento y revisión técnica — v0.6.1

## Propósito

Este documento explica cómo modificar Marking Studio sin romper los principios que motivaron su arquitectura. Complementa los comentarios `WHY:` del código: el comentario local explica **por qué existe una función** y esta guía explica **cómo extender el sistema**.

## Invariantes que no deben romperse

1. **La plantilla es dato, no código.** Un nuevo tipo de activo normalmente debe resolverse con JSON/Estudio visual.
2. **Preview y producción comparten motor.** No crear un renderer alternativo sólo para la UI.
3. **CSV flexible.** No introducir columnas obligatorias por fabricante en JavaScript/Python.
4. **Handoff seguro.** Marking Studio no envía trabajos de producción, movimiento ni potencia al láser.
5. **Configuración importada es read-only.** LightBurn/LaserGRBL/GRBL se inspeccionan; no se sobrescriben.
6. **No inventar identidad.** Prefijos/sufijos sólo se aplican bajo regla explícita de la plantilla.
7. **No convertir investigación en preset validado.** La validación física pertenece al taller.

## Añadir una nueva plantilla

Preferencia: hacerlo desde **Estudio visual**.

1. Crear o duplicar plantilla.
2. Definir ancho/alto.
3. Crear campos (`serial`, `economico`, etc.).
4. Arrastrar texto, QR/barcode u otros elementos.
5. Definir identidad principal.
6. Configurar reglas manual/importación.
7. Probar con ejemplos.
8. Guardar.
9. Validar con CSV de una y varias columnas.
10. Realizar aceptación física antes de declarar estándar.

No debería requerir cambios en `template_engine.py` ni `main.py`.

## Añadir un nuevo tipo de elemento

Sólo es necesario modificar código si el elemento no puede representarse con los tipos existentes.

Puntos a revisar:

- `models.ElementSpec` — contrato y validación;
- `barcode_engine.py` o un motor geométrico equivalente;
- `template_engine.render_template` — despacho;
- `app/static/index.html` — herramienta del diseñador;
- `app/static/app.js` — tamaño, propiedades, preview visual;
- pruebas unitarias y SVG interoperability.

Debe documentarse el motivo del nuevo tipo con comentario `WHY:`.

## Añadir máquina o lector

Normalmente basta un JSON bajo `config/machines` o `config/scanners`. No hardcodear por nombre en frontend.

Una máquina describe capacidades e interoperabilidad; **no habilita control directo**.

## Añadir jig

1. Crear/duplicar JSON en `config/jigs`.
2. Definir slots/geometría.
3. Marcar `calibration_required: true` hasta aceptación física.
4. Generar P0/PX/PY.
5. Medir y documentar resultado.
6. Sólo después promover a estándar operativo.

## Datos y CSV

El importador debe seguir aceptando:

- listas sin encabezado;
- archivos con encabezado;
- múltiples columnas libres.

Los alias específicos (`serie`, `serial_no`, etc.) pertenecen a metadatos de plantilla, no a una tabla global de código.

## Revisión de código

Antes de aprobar un cambio:

- leer el comentario `WHY:` de la función afectada;
- confirmar si el cambio mantiene esa razón o exige actualizarla;
- revisar `docs/CODE_REVIEW_GUIDE.md`;
- ejecutar `python -m pytest`;
- ejecutar `python -m compileall -q app`;
- ejecutar `node --check app/static/app.js`;
- ejecutar los QA SVG/scan/batch/configuración relevantes;
- comprobar `/api/health` y la versión.

## Convención de comentarios

Se usa `# WHY:` en Python y `/** WHY: ... */` en JavaScript para decisiones estructurales. Estos comentarios no deben narrar literalmente cada línea; deben explicar la **intención que un revisor podría romper sin darse cuenta**.

Ejemplo bueno:

> `WHY: Preview y producción usan el mismo renderer para impedir divergencias.`

Ejemplo pobre:

> `Incrementa i en uno.`

## Versionado

- parche (`0.6.x`): QA, documentación, UX o correcciones compatibles;
- minor (`0.x.0`): capacidades nuevas compatibles;
- major: cambios incompatibles de modelo/archivo/API.

Las plantillas tienen su propio `version` y no deben depender exclusivamente de la versión de la aplicación.

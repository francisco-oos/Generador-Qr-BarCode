# Reporte de pruebas — Server Oficina Marking Studio v0.6.1

Fecha de cierre: 2026-09-12

## Resultado general

**Estado de software: PASS / listo para piloto físico controlado.**

La v0.6.1 conserva el Estudio visual de marcado, CSV/listas flexibles y exportación masiva de SVG sin cambiar el límite de seguridad: Marking Studio genera diseño y trazabilidad; el software de la grabadora continúa controlando movimiento, potencia y disparo.

## Matriz final

| Prueba | Resultado |
|---|---|
| Pytest | **55/55 PASS** |
| `compileall` | **PASS** |
| JavaScript `node --check` | **PASS** |
| API `/api/health` | **PASS · v0.6.1** |
| Catálogo/configuración | **PASS** |
| Render de todas las plantillas guardadas | **PASS** |
| Preview de plantilla visual no persistida | **PASS** |
| Contrato HTML ↔ JS | **PASS** |
| CSV 1,200 filas HTTP | **PASS** |
| Lista de una columna sin encabezado | **PASS** |
| CSV con encabezado forzado | **PASS** |
| Mapeo sin tabla de sinónimos hardcodeada en JS | **PASS** |
| Identidad física gobernada por `primary_identity_field` | **PASS** |
| Exportación masiva 1,000 SVG | **PASS** |
| Exportación masiva 5,000 SVG | **PASS** |
| Simulación de lectura | **28/28 PASS** |
| Decodificación jig INOVA 3×4 | **12/12 PASS** |
| SVG XML/svglib/Inkscape | **PASS** |
| Importadores `.clb/.lbmt/.psh/GRBL` | **4/4 PASS** |
| Simulador GRBL read-only | **PASS · sólo `$I` y `$$`** |
| Calibración P0/PX/PY | **PASS** |
| Benchmark 1,200 registros / 2,500 renders | **PASS** |
| UI navegador real | **SKIP_POLICY** |
| Fallback API/HTML de UI | **PASS** |

## Pruebas específicas del Estudio visual

Se verificó que un borrador completo puede enviarse a `/api/templates/preview` y renderizarse con el mismo `TemplateSpec`/`render_template` de producción sin guardarlo primero. Esto evita una diferencia entre “lo que se ve en el editor” y “lo que exporta el motor”.

El contrato frontend exige controles para:

- lienzo visual;
- agregar Code 128 y QR;
- guardar plantilla;
- elegir modo de encabezado del CSV;
- vista previa del primer registro;
- exportación masiva de SVG.

También se añadió una prueba que falla si reaparece la antigua tabla de sinónimos de equipo hardcodeada en JavaScript.

## CSV/listas

El parser fue ampliado para tres modos:

- `auto`;
- `yes` = primera fila es encabezado;
- `no` = sin encabezado.

La prueba con:

```text
Q00525499
Q00525500
Q00525501
```

conserva los tres valores y crea una sola columna `value`. La primera serie ya no se pierde como encabezado accidental.

Para archivos de una sola columna, el frontend propone esa columna a los campos de la plantilla; en archivos multicolumna usa nombres/alias almacenados en la propia plantilla y siempre permite corrección manual.

## Eliminación de hardcodeo operativo

Se verificó que la conciliación de lote del backend toma la identidad desde `template.metadata.primary_identity_field`; si no existe, usa el primer campo esperado y finalmente un valor no vacío genérico. Ya no existe un orden fijo de `manufacturer_id → operational_id → asset_id → ...` en el motor de lote.

Los defaults de serie INOVA también dejaron de estar en el HTML: campo, prefijo y sufijo se cargan desde la plantilla seleccionada.

## Exportación masiva

`/api/bulk/svg-export` genera un SVG por fila más manifiestos, sin G-code ni comandos de máquina.

Pruebas:

- 1,000 registros: **PASS**, 1,000 SVG presentes y contenido validado;
- 5,000 registros: **PASS**, ~5.29 MB de ZIP en este dataset; ejecución observada ~12.3 s en el host de prueba, con pico RSS ~195 MB.

El límite por solicitud es 10,000 filas para evitar trabajos no acotados. Para producción con jig se mantiene el fraccionamiento por capacidad física.

## Simulación de códigos

La batería existente mantiene **28/28** lecturas correctas sobre Code 128 y QR con:

- original;
- reducción 50 %;
- blur 0.6;
- blur 1.0;
- rotación 2°;
- contraste reducido;
- abrasión digital delgada.

El jig INOVA completo mantiene **12/12 Code 128** decodificados.

Además se generó `samples/output/visual_designer_composite.svg` y PNG 600 DPI con Code 128 + QR + textos en una plantilla arbitraria; un decodificador independiente recuperó `Q00525499` y `TEL-0037`.

## Benchmark base

Última corrida de `benchmark_scale.py`:

- registros: 1,200;
- jig: 12;
- cargas: 100;
- 2,500 renders individuales: ~5.03 s;
- ~496.6 marcas/s en este host;
- batch vectorial de 1,200: ~2.41 s;
- PNG de última cama 300 DPI: ~5.64 s;
- estado: **PASS**.

Estas cifras no prometen el mismo rendimiento en otra PC; prueban que la arquitectura no depende de datasets pequeños.

## Interoperabilidad y máquina

Todos los SVG guardados pasaron XML, svglib e Inkscape. El diagnóstico GRBL simulado transmitió exclusivamente `$I` y `$$`, con cero comandos prohibidos.

El control productivo permanece fuera de Marking Studio. La salida se entrega a Sculpfun Space, LightBurn o el flujo compatible configurado para la máquina.

## Límite de la validación

No se certifica digitalmente:

- potencia/velocidad real sobre una carcasa;
- foco real de la unidad instalada;
- contraste después del láser;
- desgaste físico;
- repetibilidad mecánica del jig;
- lectura real bajo suciedad/campo.

Eso requiere la SCULPFUN, el material real y el lector operativo. El software ya contiene el procedimiento para capturar el preset que el área utiliza, hacer Frame/calibración y verificar por escaneo.

## Auditoría de mantenibilidad y UX v0.6.1

Se añadieron pruebas de contrato que fallan si una función/clase Python pierde su explicación `WHY:`/docstring o si una función JavaScript nombrada queda sin rationale cercano. También se valida que el paquete incluya y enlace `CODE_REVIEW_GUIDE.md`, `MAINTAINER_GUIDE.md` y `UX_AND_WORKFLOW.md`.

La interfaz se revisó por objetivo operativo y ahora dispone de:

- portada por tareas;
- navegación agrupada Operación / Diseño / Control;
- `Sistema` oculto en modo guiado;
- preview individual en vivo con debounce;
- stepper visible para Datos → Mapeo → Posiciones → Salida;
- lista de capas en el Estudio visual para seleccionar objetos pequeños o superpuestos.

Los contratos HTML↔JS, IDs únicos, drag/drop y ausencia de comandos productivos de máquina permanecen en PASS.

## Browser E2E

Chromium del runtime bloqueó navegación a localhost por política (`SKIP_POLICY`). No se presenta como PASS ficticio. Se ejecutaron en su lugar:

- JavaScript syntax check;
- contrato de IDs HTML/JS;
- fallback API/static;
- health/catalog/calibración;
- pruebas de endpoints del diseñador y CSV.

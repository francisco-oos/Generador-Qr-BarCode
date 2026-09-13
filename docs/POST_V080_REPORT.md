# POST v0.8.0 — cierre funcional final

**Base PRE:** v0.7.1  
**Versión final evaluada:** v0.8.0  
**Host de validación:** Linux x86_64 · Python 3.13.5 · Node disponible  
**Fecha:** 2026-09-13

## Resumen

La evolución se realizó sobre el mismo Server Oficina Marking Studio. No se sustituyeron los motores de Code 128, Code 39, QR o Data Matrix ni la frontera de máquina. La capa nueva modela estrategia física de ablación, evidencia validada y un elemento imagen seguro dentro del Estudio Visual.

## PRE / POST

| Métrica | PRE v0.7.1 | POST v0.8.0 final |
|---|---:|---:|
| Pruebas automatizadas | 158 | **196** |
| Resultado | 158/158 PASS | **196/196 PASS** ejecutadas por grupos + regresiones focales después de los últimos cambios |
| Fabricantes hardcodeados en lógica runtime | 0 | **0** |
| Streaming directo al láser | false | **false** |
| Comandos GRBL permitidos | `$I`, `$$` | **`$I`, `$$`** |

La suite se dividió por límite del runner; todos los archivos de prueba fueron ejecutados. Tras los últimos cambios de imagen se repitieron sus pruebas y los contratos de documentación/frontend.

## Funciones finales añadidas

### Marcado físico

- `MarkingMode`: `polarity`, `polarity_scope`, `negative_field`, `field_margin_mm`, `kerf_compensation_mm`, `validated_on`/`validado_sobre`.
- Defaults positivos compatibles con el flujo histórico.
- `codes + islands`, `all + islands`, `all + template` y **`codes + template`**.
- `codes + template` se representa honestamente como **DOS ETAPAS**: `layer_background` contiene el campo de fondo/código; texto/geometría positiva conservan sus capas. Metadata `requires_secondary_operation=true` y sufijo `_NEGATIVE_2PASS`.
- `negative/all + editable` se rechaza porque requiere contornos.
- `all + template` con elementos rotados permanece bloqueado hasta poder fusionar transforms sin mentir sobre la geometría.
- kerf default `0`; no existe compensación inventada.
- unión de rectángulos compensados para evitar cancelaciones `evenodd` en módulos vecinos.
- área/ratio estimado de ablación como advertencia geométrica, nunca como receta de máquina.

### Preflight

El preflight continúa evaluando exclusivamente el símbolo **positivo canónico**. Una guardia de arquitectura falla si geometría negativa `evenodd` llega a la ruta de calidad. El negativo es instrucción de ablación, no el código que debe decodificar el lector.

### Comparación y cupón

- `/api/marking/compare`: positivo vs negativo desde el mismo renderer, con PNG opcional derivado del mismo SVG.
- `/api/marking/coupon`: cuatro combinaciones invertidas del mismo dato:
  - A codes/islands;
  - B codes/template 2PASS;
  - C all/islands;
  - D all/template.
- El positivo de referencia se mantiene en la comparación lado a lado.

### Biblioteca validada

Se reutiliza la base existente de `machine_captures/material_presets`. Puede conservar máquina, superficie, parámetros capturados, `MarkingMode`, perfil del lector, intentos/éxitos y nota de validación. No se deriva ninguna receta universal por material.

### Elemento imagen

- `ElementSpec(kind="image")`.
- PNG/JPG: threshold o Floyd–Steinberg a geometría 1-bit.
- SVG: saneado a subconjunto vectorial sin scripts, `foreignObject`, recursos externos, `use`, filtros ni texto vivo.
- contenido embebido como data URI; no quedan rutas locales/red en el artefacto.
- posición, tamaño, rotación, ID estable y capa semántica.
- advertencia al invadir caja/quiet zone de un código.
- imagen no entra al preflight de decodificación.
- `negative/codes` deja la imagen positiva; `negative/all` con imagen se rechaza hasta contar con una operación booleana general segura.
- calidad física de imagen: **PENDIENTE DE ACEPTACIÓN FÍSICA**.

## QA ejecutado en el árbol final

- `python -m compileall -q app scripts tests`: PASS.
- `node --check app/static/app.js`: PASS.
- `scripts/compatibility_check.py`: PASS.
- `qa_quality_preflight.py`: PASS; INOVA Code128 ROBUSTO 7/7, Sercel 7/7, QR teléfono 6/7, caso subdimensionado FRÁGIL.
- `qa_scan_simulation.py`: **28/28 PASS**.
- `qa_batch_decode.py`: **12/12** símbolos del lote, PASS con svglib y CairoSVG sobre SVG regenerado en la propia corrida.
- `qa_svg_interop.py`: PASS con Inkscape disponible y validación adicional svglib/CairoSVG.
- `qa_configuration_imports.py`: **4/4 PASS**.
- `qa_grbl_serial_simulator.py`: PASS; sólo `$I` y `$$`.
- `qa_browser_smoke.py`: contrato API/HTML PASS; navegador real **SKIP_POLICY** por bloqueo localhost del runtime.

### Benchmark

- 1,200 registros sobre jig de 12 → 100 cargas.
- 2,500 renders individuales: 2.108 s, ~1,185.9/s en este host.
- 1,200 marcas vectoriales: 0.979 s.
- cama final PNG 300 dpi: 5.68 s.

Los números son de este host y no son garantía de rendimiento en la PC del taller.

## Hardcode

Búsqueda runtime sobre `app/*.py` y frontend no encontró ramas ejecutables `if/case` por INOVA, Sercel, CUBOT, UMIDIGI, Xiaomi o Steren. Las menciones restantes son comentarios, ayuda o placeholders de los casos reales. Plantillas, jigs, lectores, prefijos, materiales y estrategia física siguen modelados como configuración/datos.

## Clasificación honesta

### PASS REAL en este host

Suite automatizada, compilación, sintaxis JS, API/configuración, generación SVG, QR/Code128, preflight, CSV/XLSX, modos físicos, imagen, batch, dos renderizadores, Inkscape CLI, importadores y simulador GRBL read-only.

### PASS CI / portabilidad declarada

La matriz de proyecto mantiene Windows/macOS/Python soportados; esta ejecución no equivale a una prueba física en esos sistemas.

### NO PROBADO

- importación/ejecución real en LightBurn, SCULPFUN Space o LaserGRBL durante esta sesión;
- asignación real de las dos etapas de `_NEGATIVE_2PASS` en software de máquina.

### PENDIENTE DE ACEPTACIÓN FÍSICA

- SCULPFUN S9 Pro real;
- potencia, velocidad, foco, pasadas y kerf medido;
- materiales/carcasa reales;
- acabado con marcador/pintura;
- abrasión/durabilidad;
- COM-597 sobre pieza grabada, especialmente Data Matrix según firmware;
- calidad de logos/raster en material real.

## Conclusión

v0.8.0 mantiene la finalidad original: **Estudio Visual de Marcado con plantillas reutilizables, datos variables, validación y trazabilidad**, dejando el control de máquina al software que ya funciona. El modo invertido y la imagen amplían el arte que puede producirse sin introducir ramas por fabricante ni convertir Marking Studio en controlador de láser.

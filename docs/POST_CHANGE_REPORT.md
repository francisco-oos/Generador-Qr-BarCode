# REPORTE POST — Resultado de la evolución 0.6.2 → 0.7.0

**Proyecto:** Server Oficina Marking Studio
**Versión entregada:** 0.7.0
**Base de comparación:** `docs/PRE_CHANGE_BASELINE.md` (0.6.2)
**Host de validación:** Linux x86_64, Python 3.12.3, Node.js disponible
**Fecha:** 2026-09-12

> Este documento sólo registra lo ejecutado y medido en este host. Lo no ejecutado se
> declara como NO PROBADO o PENDIENTE FÍSICO, nunca como PASS.

---

## 1. Comparación PRE / POST

| Métrica | PRE (0.6.2) | POST (0.7.0) | Cambio |
|---|---:|---:|---|
| Pruebas automatizadas | 59 | **151** | +92 |
| Resultado de la suite | 59/59 PASS | **151/151 PASS** | sin regresiones |
| Tiempo de suite | 26.66 s | 69.57 s | mayor cobertura |
| `compileall` | PASS | PASS | = |
| `node --check app.js` | PASS | PASS | = |
| `compatibility_check.py` | PASS | PASS | = |
| Arranque uvicorn + `/api/health` | PASS 200 | PASS 200 | = |
| Endpoints de API | 30 | 31 | +`/api/data/sheets` |
| Dependencias de runtime | 11 | 12 | +`openpyxl` |

### Rendimiento de render

| Registros | PRE ms/marca | POST ms/marca | PRE pico mem. | POST pico mem. | PRE SVG | POST SVG |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 14.36 | **4.16** | 0.49 MB | 0.03 MB | — | — |
| 10 | 8.12 | **2.94** | 0.62 MB | 0.01 MB | 0.06 MB | 0.02 MB |
| 100 | 8.48 | **2.98** | 1.78 MB | 0.02 MB | 0.65 MB | 0.21 MB |
| 1 000 | 8.94 | **2.87** | 2.76 MB | 0.01 MB | 6.49 MB | 2.08 MB |
| 5 000 | 9.04 | **2.98** | 2.76 MB | **0.01 MB** | 32.44 MB | **10.38 MB** |

**Lectura honesta de estos números.** La mejora de ~3× en tiempo y de ~3× en tamaño de
salida **no fue un objetivo de optimización**; es un efecto secundario de cambiar la
serialización. Al emitir un `<path>` plano en lugar de un `<svg>` anidado con `clipPath`,
`<title>`, `<desc>` y transformaciones, se elimina tanto el trabajo de composición como el
volumen de texto. El pico de memoria cae de 2.76 MB a 0.01 MB porque los fragmentos ya no
retienen árboles de objetos de la librería de dibujo.

Consecuencia práctica: 5 000 registros pasan de ~45 s a ~15 s, y una exportación de 10 000
de ~90 s a ~30 s, lo que la sitúa dentro de lo tolerable para una petición síncrona.

### Tamaño de artefactos de muestra

| Archivo | PRE | POST |
|---|---:|---:|
| `inova_Q00525499.svg` | 6 490 B | **2 075 B** |
| `inova_batch_12.svg` | 77 216 B | **21 421 B** |

---

## 2. Estado de cada brecha identificada en el PRE

| # | Brecha PRE | Estado POST | Evidencia |
|---|---|---|---|
| 18, 19 | Capas/grupos semánticos en SVG | **RESUELTO** | `layer_codes`, `layer_text`, `layer_geometry`, `layer_registration`, `layer_guides` |
| 18 | `id` estables y comprensibles | **RESUELTO** | `barcode_serial`, `text_serial`; `mark_0001__barcode_serial` en lotes |
| 5.2 | Identificadores duplicados | **RESUELTO** | lote de 12: 40 `id`, **0 duplicados**; prueba dedicada que falla si alguno se repite |
| 19 | `inkscape:groupmode` / `inkscape:label` | **RESUELTO** | sólo en modo editable; producción queda libre de extensiones de un editor |
| 19, 20 | Maestro editable vs producción | **RESUELTO** | `export_mode` en API y selector en la interfaz |
| 8, 9 | Importación XLSX y selector de hoja | **RESUELTO** | `app/tabular.py`, `POST /api/data/sheets` |
| 9 | Vista previa 20–50 registros | **RESUELTO** | configurable, 25 por defecto, 500 máximo |
| 13 | Transformaciones de datos | **RESUELTO** | `lowercase`, `pad_zeros_to`, `derived_fields` |
| 17 | Patrón de nombre de archivo | **RESUELTO** | `{economico}_{serial}` con saneado multiplataforma |
| 4 | Undo / redo | **RESUELTO** | historial acotado, arrastre = una operación lógica |
| 4 | Snap, alineación, distribución, selección múltiple | **RESUELTO** | imantado desactivable; 6 alineaciones + 2 distribuciones en mm |
| 6 | Rotación de elementos | **RESUELTO** | `rotation_deg`, giros rápidos y ángulo libre |
| 6 | Quiet zone por elemento | **RESUELTO** | `quiet_modules`, con advertencia sin bloqueo |
| 12 | Mapeo interactivo con resaltado cruzado | **RESUELTO** | panel ↔ tabla de datos ↔ lienzo |
| 16 | Selector de modo de salida | **RESUELTO** | jig / individual / ambos, ortogonal al tipo de SVG |
| 37 | Navegación de registros | **RESUELTO** | primero / anterior / siguiente / último / aleatorio |
| 39 | 10 000 registros por petición | **MEJORADO** | ~30 s estimados frente a ~90 s; sigue siendo el límite superior recomendado |
| 22 | Reimportar ajustes desde SVG | **NO IMPLEMENTADO — habilitado** | ver §6 |
| 4 | Zoom y pan del lienzo | **NO IMPLEMENTADO** | ver §6 |
| 5 | Ocultar / bloquear / renombrar capas | **PARCIAL** | renombrado vía etiqueta; visibilidad y bloqueo pendientes |

---

## 3. Defectos reales corregidos, con su demostración

### 3.1 Identificadores duplicados en el documento SVG

**Síntoma medido en PRE.** `samples/output/inova_batch_12.svg` contenía 37 identificadores,
de los cuales `mark`, `clip` y `group` aparecían **12 veces cada uno**. Reproducido en el
motor con dos Code 128 de longitud distinta: dos `clipPath id="clip"` de anchos 76.39 y
207.35 en el mismo documento, ambos referenciados por `url(#clip)`.

**Por qué importa.** `id` es de tipo ID en XML y debe ser único. Un renderizador conforme
resuelve `url(#clip)` contra la primera coincidencia, de modo que el símbolo más largo
queda sujeto al recorte del más corto.

**Alcance honesto.** Con `svglib` —el renderizador de la ruta de producción— no se llegó a
reproducir truncamiento visible; svglib es tolerante en este punto. El riesgo era **latente
pero comprobable**, no una falla de producción demostrada.

**Corrección.** Toda la construcción del documento se concentró en `app/svg_document.py`,
con un `IdRegistry` que garantiza unicidad y prefijo por marca en lotes. Además se eliminó
la causa raíz: los símbolos ya no se insertan como `<svg>` anidado con `clipPath`, sino
como `<path>` plano en milímetros absolutos.

**Verificación POST.** Lote de 12 marcas: 40 identificadores, **0 duplicados**. Las diez
muestras regeneradas en `samples/output/` tienen 0 duplicados. Prueba
`test_batch_namespaces_every_mark_so_no_id_repeats_anywhere` falla si alguno reaparece, y
comprueba explícitamente que `clip` y `group` no vuelvan a existir.

### 3.2 El preflight evaluaba la quiet zone equivocada

**Encontrado durante la implementación de la quiet zone por elemento.** `_fragment_for_element`
usaba `quality.qr_quiet_modules` en lugar del valor del elemento. En cuanto un usuario
redujera la quiet zone de un código concreto, el preflight seguiría evaluando el margen del
perfil.

**Por qué importa.** Es exactamente el escenario que el preflight existe para impedir: un
código con el margen recortado a mano habría obtenido un PASS digital y habría fallado
sobre la pieza física.

**Corrección y verificación.** El preflight evalúa el valor del elemento y la quiet zone
pasó a ser un criterio propio de clasificación, no un número informativo. Un QR con quiet
zone de 1 módulo frente a los 4 de referencia se clasifica ahora como FRÁGIL.
Prueba: `test_preflight_evaluates_the_element_quiet_zone_not_the_profile`.

### 3.3 Nombre inconsistente del modo de exportación

**Encontrado durante la verificación del paquete**, no durante el desarrollo. `/api/render`
y `/api/templates/preview` llamaban `svg_mode` a «qué tipo de SVG generar», mientras que
los endpoints de lote lo llamaban `export_mode`.

**Por qué importa.** Pydantic ignora los campos desconocidos. Un cliente que pidiera
`export_mode: "editable"` a `/api/render` recibía el modo producción **sin ningún error**,
y sólo lo descubriría al abrir el archivo y no encontrar el texto editable.

**Corrección.** Ambos nombres son válidos en los dos sitios, mediante `AliasChoices`.
Pruebas: `test_svg_mode_and_export_mode_are_interchangeable_on_single_artifact_requests` y
`test_editable_mode_actually_differs_from_production_over_the_api`, que comprueba que los
dos modos devuelven realmente artefactos distintos — un alias no sirve de nada si ambos
modos producen el mismo archivo.

### 3.4 Las pruebas dependían del orden de ejecución

**Encontrado al verificar sobre un árbol sin base de datos previa.** El esquema SQLite se
crea en el `lifespan` de FastAPI, que sólo se ejecuta si el `TestClient` se usa como
context manager. Varias pruebas lo instancian directamente y funcionaban únicamente porque
otra prueba de la misma sesión ya había creado la base.

**Síntoma.** La suite completa pasaba, pero ejecutar un solo archivo sobre una instalación
limpia fallaba con `no such table: engraving_jobs` — un error desconcertante para quien
mantiene el proyecto.

**Corrección.** `tests/conftest.py` inicializa el esquema una vez por sesión. Verificado
que **los 20 archivos de prueba pasan ejecutados de forma aislada**, borrando la base entre
cada uno.

### 3.5 Falso positivo en el propio análisis de línea base

No era un defecto del proyecto sino del análisis. Se concluyó que un renderizador
independiente fallaba, cuando la causa era medir densidad de tinta sobre una imagen RGBA
con `.convert('L')`, que convierte los píxeles transparentes en negro.

Documentado íntegramente en `docs/PRE_CHANGE_BASELINE.md` §5.3, con el registro del error,
la medición corregida y la medida preventiva. Ver §5 de este documento.

---

## 4. Validación cruzada con dos renderizadores

Rasterización a 600 dpi de las cinco plantillas del catálogo, en ambas modalidades de
exportación, con composición correcta del canal alfa:

| Plantilla | Modo | Densidad svglib | Densidad CairoSVG | Decodificación |
|---|---|---:|---:|---|
| `generic_asset_qr_v1` | producción / editable | 0.0891 | 0.0980 | `RADIO-000184` |
| `inova_quantum_code128_v1` | producción / editable | 0.2370 | 0.2457 | `Q00525499` |
| `phone_qr_economic_v1` | producción / editable | 0.0951 | 0.1019 | `PHONE-000037` |
| `sercel_dfu_code128_v1` | producción / editable | 0.2249 | 0.2321 | `4281847` |
| `sercel_dfu_datamatrix_v1` | producción / editable | 0.2053 | 0.2117 | — (ver nota) |

Los dos motores coinciden dentro de un 3–4 %, diferencia atribuible al antialiasing. Que
coincidan es lo relevante: el archivo ya no depende de las tolerancias de una sola librería.

**Nota sobre Data Matrix.** `pyzbar` no decodifica Data Matrix porque `zbar` no implementa
esa simbología. **No es un defecto del símbolo generado ni una regresión**; es una
limitación conocida del decodificador. La verificación de Data Matrix queda como
**PENDIENTE FÍSICO** con el lector real.

### Decodificación de lote completo

`samples/output/inova_batch_12_300dpi.png` regenerado con 0.7.0 decodifica **12/12**
Code 128 correctos (`Q00525499` … `Q00525510`).

---

## 5. Mejora del rigor de la evidencia

El PRE observó que algunos PASS eran más débiles que la afirmación que respaldaban.
Cambios adoptados:

| Observación PRE | Acción |
|---|---|
| `convert('L')` sobre RGBA produce falsos positivos | `app/raster_probe.py` como punto único: `RGBA → composición sobre blanco → gris → análisis`. Copia duplicada eliminada de `test_svg_structure.py` |
| Un test podía medir tinta sobre transparencia | `test_no_test_measures_ink_density_on_raw_alpha` **falla** si cualquier prueba vuelve a usar `convert('L')` |
| El falso positivo podía repetirse sin aviso | `test_flatten_on_white_is_what_prevents_the_documented_false_positive` lo reproduce explícitamente: 1.0 con el método ingenuo, 0.0 con el correcto |
| Herramienta ausente reportada como PASS | `rasterize_independent` y `decode_symbols` devuelven `None` cuando la herramienta no está; las pruebas hacen `skip` con motivo, nunca PASS |
| IDs duplicados no estaban cubiertos | Prueba dedicada sobre todo el documento de lote |

---

## 6. Pendientes reconocidos

Se declaran explícitamente en lugar de darse por implícitos.

### No implementado, deliberadamente

- **Reimportación de ajustes desde SVG** (sección 22 del encargo). No se implementó, pero
  **queda habilitado**: los identificadores estables y legibles y la geometría en
  milímetros absolutos son precisamente los requisitos que faltaban. Hoy es posible abrir
  `Q00525499.svg` en Inkscape, mover `barcode_serial` de X=12 a X=14, leer el valor y
  escribirlo en el diseñador. La lectura automática de vuelta sigue siendo una función
  futura.
- **Zoom y pan del lienzo.** El lienzo se autoescala al tamaño de la plantilla. Para
  formatos de 50 × 18 mm el zoom aporta poco frente a la complejidad que añade.
- **Ocultar y bloquear capas.** El renombrado existe vía la etiqueta del elemento. La
  visibilidad y el bloqueo quedan pendientes; la lista de capas ya cubre el problema real
  que motivaba la función, que era seleccionar objetos pequeños o superpuestos.
- **Soporte de `.xls` y `.ods`.** Descartado con justificación en `docs/DATA_INGESTION.md`.
- **Imagen / logo como tipo de elemento.** No se añadió: incorporar rasterizado de imágenes
  al SVG productivo tiene implicaciones de calidad de grabado que no pueden decidirse sin
  prueba física previa.

### NO PROBADO en este host

- **Inkscape**: binario no disponible. El script `qa_svg_interop.py` lo omite y lo reporta
  como `SKIP`, no como PASS. La interoperabilidad se validó con dos renderizadores
  (svglib y CairoSVG) y con parser XML.
- **LightBurn, Sculpfun Space, LaserGRBL**: sin acceso.
- **Puerto serial GRBL físico**: sin hardware.
- **Windows y macOS**: `compatibility_check.py` verifica portabilidad de fuentes y
  empaquetado, pero sólo se ejecuta este sistema operativo. La matriz de CI cubre
  Windows / macOS y Python 3.13; eso es **PASS CI**, no PASS real.

### PENDIENTE DE ACEPTACIÓN FÍSICA

Nada de lo siguiente se ha comprobado y **no debe darse por validado**:

- grabado real sobre plástico, policarbonato, PMMA, carcasa INOVA, Sercel o teléfono;
- foco, potencia, velocidad, número de pasadas y contraste láser reales;
- resistencia a abrasión;
- lectura con el Steren COM-597 físico, en particular de **Data Matrix**, que el
  decodificador digital no puede verificar;
- comportamiento de un código rotado 90° sobre una superficie curva;
- efecto real de una quiet zone reducida sobre una carcasa con bordes o serigrafía.

Un PASS digital no sustituye el piloto físico con máquina, material y lector reales.

---

## 7. Clasificación de resultados POST (sección 51 del encargo)

| Clase | Elementos |
|---|---|
| **PASS REAL** | pytest 151/151; `compileall`; `node --check`; `compatibility_check.py`; arranque uvicorn y `/api/health` 200; generación SVG en ambos modos; rasterización con svglib y CairoSVG; decodificación pyzbar de Code 128 y QR; ingesta CSV y XLSX multi-hoja; exportación de lote; exportación individual; preflight; benchmark 1–5 000; `qa_scan_simulation`, `qa_quality_preflight`, `qa_svg_interop`, `qa_configuration_imports`, `qa_grbl_serial_simulator`, `qa_batch_decode`, `benchmark_scale` |
| **PASS CI** | matriz Windows / macOS / Python 3.13 declarada en `.github/workflows/ci.yml` |
| **NO PROBADO** | Inkscape, LightBurn, Sculpfun Space, LaserGRBL, GRBL por puerto serial, decodificación de Data Matrix |
| **PENDIENTE FÍSICO** | todo lo listado en §6 |

---

## 8. Conclusión

La evolución se hizo **sobre el mismo proyecto**. No se sustituyó ningún motor de
generación: Code 128, Code 39, QR y Data Matrix siguen usando `reportlab.graphics.barcode`
y `qrcode`, las mismas librerías que 0.6.2. Lo que cambió es la serialización del
documento, la ingesta de datos y la interacción del diseñador.

Los invariantes de seguridad permanecen intactos y probados: `SAFE_GRBL_COMMANDS` limitado
a `$I` y `$$`, `direct_laser_job_streaming: false`, conciliación física bloqueante, guías
del jig separadas del archivo productivo y la regla de prefijos que impide duplicar un
identificador importado.

Se corrigieron cuatro defectos reales del proyecto —identificadores duplicados, quiet zone
mal evaluada en el preflight, nombre inconsistente del modo de exportación y dependencia de
orden entre pruebas— y un error del propio análisis de línea base, este último documentado
en lugar de suprimido. Los dos últimos defectos aparecieron **al verificar desde el ZIP
extraído**, que es exactamente la razón por la que ese paso existe.

El software queda listo para un **piloto físico controlado**. La aceptación final sigue
dependiendo del grabado real, el material real y el lector real.

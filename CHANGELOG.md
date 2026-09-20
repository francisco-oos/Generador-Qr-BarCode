# Changelog

## 0.9.0 — experimental Laser Design Studio

- Adds parametric papel picado generation.
- Adds raster-to-halftone cut geometry.
- Adds raster-to-stencil conversion with automatic material bridges.
- Adds manufacturability preflight and minimum safe-scale calculation.
- Adds separate `/laser-design` guided UI.
- Adds OpenAI Experimental Lab Bridge Ladder coupon and reproducible Design Genome.\n- Adds Material DNA Passport for sacrificial bridge/hole/gap characterization and Self-Guarding Geometry constraints.
- Keeps all machine control outside Marking Studio.

## 0.8.0 — 2026-09-13

Evolución del modo negativo puntual de 0.7.1 hacia un modelo físico versionado y auditable. No se sustituyeron los motores matemáticos de Code 128, Code 39, QR ni Data Matrix, ni la frontera de máquina.

### Estrategia física

- Nuevo `MarkingMode` en `TemplateSpec`: `polarity`, `polarity_scope`, `negative_field`, `field_margin_mm`, `kerf_compensation_mm` y `validated_on`.
- Defaults compatibles: `positive / codes / islands / 0 / 0`; las plantillas existentes siguen siendo directas.
- Override temporal por trabajo en Generador/Lotes; sólo se persiste al pulsar explícitamente **Guardar en la plantilla**.
- Si cambia la huella física (polaridad/alcance/campo/margen/kerf) y el usuario no subió versión manualmente, el guardado incrementa la versión menor de la plantilla.
- El viejo `ElementSpec.engraving_mode` de 0.7.1 se conserva sólo como compatibilidad/migración.

### Geometría negativa

- `codes + islands`: invierte sólo códigos; texto/otros elementos siguen positivos.
- `all + islands`: texto pasa a contorno, líneas y rectángulos a áreas, conservando IDs/capas/transforms.
- `all + template`: un único campo con contenido recortado; se documenta pérdida de estructura por elemento.
- `codes + template`: habilitado como artefacto explícito de **DOS ETAPAS**. El campo negativo vive en `layer_background`, el contenido positivo conserva capas semánticas, el SVG declara `requires_secondary_operation=true` y el nombre usa `_NEGATIVE_2PASS`. Marking Studio no transmite ni ejecuta las dos pasadas.
- `all + editable`: bloqueado porque el texto debe convertirse a curvas.
- `all + template` con elementos rotados: bloqueado hasta disponer de transformación/fusión de paths verificada.
- `field_margin_mm` expande sólo el campo sacrificable.
- `kerf_compensation_mm` es recuperación TOTAL medida; 0 no altera geometría. Para 1D se compensa X; para 2D X/Y.
- Añadida unión de rectángulos compensados antes de usarlos como huecos `even-odd`, evitando cancelación de paridad cuando módulos QR/Data Matrix vecinos se solapan tras compensar. Sin librería booleana externa.

### Calidad y seguridad

- El preflight siempre evalúa la geometría positiva canónica, aunque la salida solicitada sea negativa; una guardia falla si llega geometría `even-odd` a esa ruta.
- Artefactos negativos usan sufijo `_NEGATIVE` y registran modo completo en SVG, manifiesto e histórico.
- `README_FIRST.txt` de exportaciones negativas advierte que el archivo describe ablación invertida.
- Se calcula área/ratio geométrico de ablación y se avisa al aproximarse o superar 45 % del lienzo.
- La UI oculta controles avanzados mientras la polaridad sea positiva. `codes + template` se permite, pero se rotula inequívocamente como “2 etapas” y muestra advertencia operacional.

### Comparación y caracterización

- Nuevo `POST /api/marking/compare`: positivo y negativo desde el mismo renderer; opcionalmente devuelve PNG de ambos rasterizados desde esos SVG exactos.
- Nuevo `POST /api/marking/coupon`: pieza de descarte con las **cuatro combinaciones invertidas** sobre la misma identidad: A codes/islands, B codes/template 2PASS, C all/islands y D all/template. El positivo se compara aparte mediante `/api/marking/compare`.
- Comparación lado a lado disponible en Generador y Estudio visual.

### Biblioteca validada

- Los presets locales del área pueden registrar el `MarkingMode`, lector, resultado de lectura, intentos y éxitos además de máquina/superficie/velocidad/potencia/pasadas/foco.
- Se reutiliza `machine_captures/material_presets`; no se creó una base paralela.

### Verificación

- Suite ampliada a **196 tests recolectados** en la final, incluyendo elemento imagen, sanitización y las cuatro combinaciones físicas. El resultado de ejecución final se conserva en `docs/TEST_REPORT.md` / `FINAL_VERIFICATION.json`.
- `compileall`, `node --check`, `compatibility_check`, preflight, 28/28 simulaciones, lote regenerado con svglib/CairoSVG, Inkscape CLI, importadores 4/4 y simulador GRBL `$I/$$`: PASS.
- Benchmark repetido: 2,500 renders ~1,199.9/s; 1,200 marcas vectoriales ~0.965 s.
- LightBurn/Sculpfun Space físicos y `fill-rule` en esos programas: **NO PROBADO**. Kerf/material/contraste/durabilidad/COM-597 físico: **PENDIENTE DE ACEPTACIÓN FÍSICA**.

### Elemento imagen

- Nuevo `ElementSpec(kind="image")` en el mismo Estudio Visual; no se creó una aplicación paralela ni un segundo renderer.
- PNG/JPG embebidos se convierten a geometría vectorial binaria mediante **threshold** o **Floyd–Steinberg** usando Pillow ya presente; no se añadió una librería de vectorización pesada.
- SVG subido se sanea a un subconjunto vectorial: se rechazan `script`, `foreignObject`, imágenes/referencias externas, `use`, filtros y texto vivo; colores se normalizan a geometría de grabado.
- Imagen conserva posición, tamaño, rotación, ID estable y capa semántica. El frontend permite cargar/reemplazar y elegir procesamiento.
- El motor advierte si la caja de una imagen invade el área/quiet zone de un código. Imagen no participa en el preflight de decodificación.
- `negative + scope=all` con imagen se rechaza por ahora: un SVG arbitrario saneado no se fusiona como hueco sin un booleano general. `scope=codes` mantiene la imagen positiva.
- Calidad física de raster/vector sobre material real permanece **PENDIENTE DE ACEPTACIÓN FÍSICA**.


## 0.7.1 — 2026-09-13

### Grabado negativo / relieve

- Nuevo `engraving_mode` declarativo por elemento de código: `positive` (compatibilidad histórica) o `negative_background`.
- `negative_background` genera el complemento vectorial del símbolo: graba fondo/espacios/quiet zone y deja barras o módulos como islas sin grabar. Está pensado para ensayos de relieve y posterior marcador/relleno, sin asumir lectura directa de polaridad invertida.
- El modo sólo es válido para Code 128, Code 39, QR y Data Matrix; texto/geometría auxiliar lo rechazan por validación de modelo.
- El Estudio visual incorpora selector de estrategia y muestra `NEG` en el lienzo simplificado. La Vista real SVG sigue siendo la autoridad productiva.
- El preflight expone `physical_validation_required` para esta estrategia y deja explícito que la prueba digital valida la geometría canónica, no el contraste final del material.
- Añadidas pruebas de complemento vectorial y round-trip óptico simulado para Code 128 y QR.

### Auditoría documental

- Corregido el docstring residual de `code_geometry.py` que todavía afirmaba el falso positivo de CairoSVG ya corregido en PRE/POST.
- Corregido en README el contador 149 → 151 de la suite 0.7.0.
- Consolidado `docs/TEST_REPORT.md` para retirar el bloque antiguo de 0.6.2 que podía confundirse con el estado vigente.
- Añadido `docs/NEGATIVE_ENGRAVING_AND_RELIEF.md` con alcance, riesgos, referencias y procedimiento de aceptación.

## 0.7.0 — 2026-09-12

Evolución funcional del Estudio visual de marcado. No se sustituyó ningún motor de
generación: Code 128, Code 39, QR y Data Matrix siguen usando las mismas librerías que
0.6.2. Lo que cambió es la serialización del documento, la ingesta de datos y la
interacción del diseñador.

### SVG estructuralmente saneado

- **Corregido un defecto real de 0.6.2:** el documento emitía identificadores repetidos
  (`mark`, `clip`, `group`) en cuanto contenía más de un símbolo. Un lote de 12 marcas
  producía 36 `id` duplicados, lo que viola la unicidad de `id` de XML/SVG y permite que
  dos símbolos distintos referencien el mismo recurso `url(#…)`.
- Toda la construcción del documento se concentra en `app/svg_document.py`. Ningún otro
  módulo escribe la cabecera `<svg>`.
- Capas semánticas explícitas y ordenadas: `layer_background`, `layer_geometry`,
  `layer_codes`, `layer_text`, `layer_registration`, `layer_guides`.
- Identificadores legibles y estables por elemento (`barcode_serial`, `text_serial`) en
  lugar de nombres generados por librerías externas.
- En lotes, cada posición recibe su propio espacio de nombres (`mark_0001__barcode_serial`),
  de modo que la unicidad es estructural y no depende de revisar cada generador.
- La geometría de los símbolos se emite como `<path>` plano en milímetros absolutos del
  lienzo, sin `<svg>` anidado, `clipPath` ni `transform="scale(1,-1)"`.
- Dos modalidades de exportación: **maestro editable** (texto como texto, atributos
  `inkscape:groupmode` / `inkscape:label`) y **producción**.

### Ingesta de datos

- Nuevo `app/tabular.py`: lectura unificada de CSV, TXT y **XLSX**.
- Nuevo endpoint `POST /api/data/sheets` para listar hojas antes de interpretar el libro.
- `POST /api/csv/inspect` acepta ahora XLSX y admite `sheet` y `preview_limit`. Los campos
  previos (`headers`, `count`, `rows`, `preview`, `header_mode`) conservan su significado.
- **Nunca se asume la primera hoja.** Un libro que empieza con una portada o un
  instructivo no debe leerse en silencio.
- El formato se detecta por firma de archivo, no sólo por extensión.
- Un identificador numérico de Excel (`4281847`) se convierte a texto sin decimal.
- Encabezados duplicados se desambiguan (`serial`, `serial_2`) en lugar de sobrescribirse.
- El formato `.xls` heredado se rechaza con un mensaje accionable en lugar de fallar de
  forma opaca. Descartado `xlrd` deliberadamente.
- Nueva dependencia: `openpyxl==3.1.5` (MIT, sin dependencias nativas).

### Transformaciones declarativas de datos

- `InputRule` añade `lowercase` y `pad_zeros_to`. El relleno con ceros recupera el `00184`
  que Excel pierde al tratar el valor como número; nunca recorta un valor más largo.
- `uppercase` y `lowercase` simultáneos se rechazan al guardar la plantilla.
- Nuevo `derived_fields` para composición simple (`{serial}-{economico}`). Es sustitución
  de marcadores y texto literal, **no** un lenguaje de expresiones.
- **Orden fijo y documentado:** recorte → caja → relleno → prefijo/sufijo → campos
  derivados. El orden afecta el resultado y por eso es parte del contrato.
- Invariante conservado: un valor importado que ya trae su prefijo no se duplica.

### Estudio visual

- **Rotación** por elemento (`rotation_deg`), normalizada a 0–360, con giros rápidos de
  0/90/180/270 y ángulo libre. Se emite como `transform` sobre el grupo del elemento y
  no horneada en la geometría, de modo que sigue siendo una propiedad medible y editable.
- **Quiet zone por elemento** (`quiet_modules`). Vacío hereda el perfil de calidad; `0`
  explícito se conserva como decisión del usuario. Reducirla emite advertencia y no
  bloquea la exportación.
- **Corregido:** el preflight evaluaba la quiet zone del perfil en lugar de la del
  elemento, de modo que un código con margen recortado a mano pasaba la validación.
- **Undo/redo** con historial acotado. Un arrastre completo es una sola operación lógica.
  Cubre mover, redimensionar, agregar, borrar, duplicar, rotar, desplazar con flechas y
  alinear. Botones y atajos Ctrl+Z / Ctrl+Y, activos sólo en la pestaña de diseño.
- **Imantado** desactivable con rejilla configurable, a rejilla, centro del lienzo y
  bordes/centros de otros elementos. Tolerancia expresada en píxeles de pantalla para que
  el ajuste fino con zoom no se vuelva imposible. Guías transitorias que nunca se exportan.
- **Selección múltiple** con Ctrl/Shift+clic, en lienzo y en la lista de capas.
- **Alineación** izquierda/centro/derecha, superior/centro/inferior, y distribución
  horizontal y vertical, siempre sobre milímetros físicos.

### Mapeo interactivo y producción

- Cada fila del panel de mapeo muestra qué elementos de la plantilla consume esa columna.
- Resaltado cruzado: al enfocar un campo se iluminan la fila del panel, la columna de la
  tabla de datos y el elemento en el lienzo, con un color distinto del de selección.
- Tabla de vista previa de datos con número de filas configurable.
- Navegación de registros: primero, anterior, siguiente, último y aleatorio, con
  recálculo inmediato de la vista real.
- Selector unificado de modo de salida (jig / individual / ambos), **independiente** del
  tipo de SVG (producción / maestro editable). Son decisiones ortogonales.
- Patrón libre de nombre de archivo (`{economico}_{serial}`), saneado contra las
  restricciones de Windows, Linux y macOS y contra nombres reservados.

### Hallazgos de la verificación del paquete

Ambos se encontraron ejecutando la verificación desde el ZIP extraído, no durante el
desarrollo, que es precisamente para lo que sirve ese paso.

- **Nombre inconsistente del modo de exportación.** El concepto «qué tipo de SVG generar»
  se llamaba `svg_mode` en los endpoints de artefacto único y `export_mode` en los de
  lote. Pydantic ignora los campos desconocidos, así que un cliente que usara el nombre
  del otro endpoint recibía producción **en silencio** y sólo lo descubría al abrir el
  archivo. Ahora ambos nombres son válidos en los dos sitios.
- **Aislamiento de pruebas.** El esquema SQLite se crea en el `lifespan` de FastAPI, que
  sólo corre si el `TestClient` se usa como context manager. La suite completa pasaba,
  pero ejecutar un solo archivo sobre una instalación limpia fallaba con
  `no such table: engraving_jobs`. Añadido `tests/conftest.py` que inicializa el esquema
  una vez por sesión. Verificado que los 20 archivos de prueba corren aislados.

### Pruebas y rigor de la evidencia

- Suite: **59 → 151 pruebas**, todas en verde.
- Nuevo `app/raster_probe.py`: punto único de rasterización y análisis con composición
  correcta del canal alfa sobre fondo blanco.
- **Corregido un error del propio análisis de línea base**, no del proyecto: se había
  concluido que un renderizador independiente fallaba, cuando la causa era medir densidad
  de tinta sobre una imagen RGBA con `.convert('L')`. Ver `docs/PRE_CHANGE_BASELINE.md`
  §5.3.
- Guardia permanente: una prueba falla si cualquier test vuelve a medir tinta sobre
  transparencia sin normalizar el fondo.
- Prueba específica que falla si cualquier `id` se repite en un documento de lote.
- Casos de ingesta reales: celdas vacías, columnas duplicadas, encabezados con espacios y
  acentos, caracteres especiales, una sola fila y 5 000 filas.

## 0.6.2 — 2026-09-12

- Añadido preflight de legibilidad `/api/quality/check` para plantillas guardadas o borradores del diseñador.
- Clasificación por código: ROBUSTO / ACEPTABLE / FRÁGIL / NO LEGIBLE.
- Validación de módulo físico contra el perfil de calidad, límites del lienzo y simbología declarada por el lector seleccionado.
- Prueba digital opcional de rasterización + decodificación exacta bajo reducción, blur, contraste, rotación y abrasión fina.
- `pyzbar` pasa a dependencia de runtime opcional-funcional; si `libzbar` no está disponible la app continúa con análisis geométrico y lo reporta claramente.
- El lienzo visual se identifica como representación NO escaneable; la Vista real SVG se identifica como el render productivo ESCANEABLE.
- Generador individual y Estudio visual incorporan selector de lector y botón de prueba de legibilidad.
- Advertencias automáticas al usar módulos inferiores al perfil conservador.
- Documentado el riesgo de reescalado al imprimir/importar: SVG debe mantenerse a 100 % de tamaño físico.
- Añadidas pruebas unitarias/API/UX del nuevo preflight; suite total: 59 pruebas automatizadas.
- Evidencia de campo inicial: fotografía de hoja impresa decodificó `TEL-0037` (QR) y `4281847` (Code 128); confirmación de `Q00525499` queda reservada al lector físico.

## 0.6.1 — 2026-09-12

- Auditoría de mantenibilidad: comentarios `WHY:` junto a todas las funciones/clases Python y funciones JavaScript nombradas, explicando intención y límites.
- Añadida `CODE_REVIEW_GUIDE.md` con inventario de módulos, símbolos, línea y razón de existir para revisión posterior.
- Añadidas `MAINTAINER_GUIDE.md` y `UX_AND_WORKFLOW.md` con invariantes, extensión sin hardcodeo y razonamiento de interfaz.
- Interfaz reorganizada por tarea: Inicio, Operación, Diseño y Control; `Sistema` queda oculto en modo guiado.
- Nueva portada con acciones frecuentes y resumen de catálogo.
- Preview individual en vivo mientras se captura, con debounce para no saturar el backend.
- Lotes/CSV muestran stepper Datos → Mapeo → Posiciones → Salida.
- Estudio visual añade lista de capas/elementos para seleccionar objetos pequeños o superpuestos.
- QA ampliado con contratos de documentación/UX y validación visual por Chromium en el host de pruebas.

## 0.6.0 — 2026-09-12

- Replanteado el producto como **Estudio visual de marcado con plantillas**, no sólo selector de perfiles predefinidos.
- Añadido diseñador visual: crear/duplicar plantilla, agregar texto/serie, texto fijo, Code 128, Code 39, QR, Data Matrix, rectángulo y línea; arrastrar elementos y ajustar geometría en mm.
- Añadida vista real SVG en vivo usando el mismo motor de renderizado productivo mediante `/api/templates/preview`; el borrador no se persiste hasta guardarlo.
- Añadidos campos de datos configurables, identidad principal por plantilla y reglas de prefijo/sufijo aplicables al borrador.
- Eliminado del frontend el orden rígido de IDs y la tabla fija de sinónimos de CSV; los alias pasan a `metadata.csv_aliases` de cada plantilla.
- CSV ampliado con detección automática/forzada de encabezados y soporte de listas de una sola columna sin perder la primera serie.
- Cuando sólo hay una columna, se propone automáticamente para los campos de la plantilla; el mapeo continúa siendo editable.
- Añadida vista previa del primer registro CSV al cambiar el mapeo.
- Añadida exportación masiva de **un SVG por fila** hasta 10 000 registros, además del flujo por jig.
- Eliminados defaults INOVA específicos del generador de series; ahora toma campo/prefijo/sufijo desde la plantilla seleccionada.
- Mantiene el handoff seguro: Marking Studio genera arte; LightBurn/Sculpfun Space/LaserGRBL controla la máquina.
- QA ampliado a 48 pruebas automatizadas; exportación masiva validada con 1 000 y 5 000 SVG; 28/28 simulaciones de lectura y 12/12 Code 128 del jig.
- Documentación añadida/actualizada: `VISUAL_TEMPLATE_STUDIO.md`, manual rápido, arquitectura y guía CSV.

## 0.5.1 — 2026-09-12

- Identificado e incorporado el lector real Steren COM-597 visto en la fotografía.
- Perfil 1D/2D con Code 128, QR y Data Matrix; contraste documental >30 %.
- QA específico: la plantilla QR de teléfono mantiene módulo 0.50 mm (~19.7 mil), con margen sobre los 8.7 mil documentados para QR.
- Se mantiene Code 128 para nodos y QR para teléfonos; el mismo COM-597 puede verificar ambos.
- Documentado procedimiento de aceptación física específico para el lector.

## 0.5.0 — 2026-09-12

- Añadidos modos **Guiado** y **Experto**.
- Añadida calibración de jig P0/PX/PY, SVG de referencia y evaluación de traslación/escala/escuadra.
- Corregida la referencia de foco S9 Pro a **50 mm** según el manual oficial revisado.
- Añadido handoff/documentación de Sculpfun Space.
- Añadida captura manual de presets ya validados por el área.
- Añadida detección/importación read-only de bases de materiales LaserGRBL `.psh`.
- Ampliada detección/importación LightBurn y documentación de Material Test.
- Ampliadas pruebas CSV, calibración, API, SVG/Inkscape, browser-fallback y compatibilidad.
- Añadida prueba HTTP multipart con CSV real de 1,200 registros y QA independiente 4/4 de importadores `.clb`, `.lbmt`, `.psh` y dump GRBL.
- SVG de calibración validado además por XML, svglib e Inkscape, separado explícitamente de las salidas productivas.
- Añadidos `MANUAL_RAPIDO.md`, `CALIBRATION_AND_ALIGNMENT.md` y `SOFTWARE_HANDOFF_AND_MACHINE_SETTINGS.md`.

## 0.4.0 — 2026-09-12

- Añadida biblioteca de referencias de materiales separada de los presets productivos del taller.
- Añadidas fichas de riesgo para PVC/vinilo, ABS, policarbonato, goma desconocida y composites de fibra de vidrio sin resina identificada; no se generan presets productivos para ellos.
- Añadidas referencias iniciales de superficies para CUBOT KingKong 9, UMIDIGI BISON X10/X10 Pro y Xiaomi/Redmi.
- Añadida UI **Materiales / Presets** con buscador de materiales y consulta de modelos de teléfono.
- Añadido parser de LightBurn Material Test `.lbmt` y preferencias `.lbprefs`/`prefs.ini`.
- Añadida detección local read-only de artefactos LightBurn en rutas convencionales de Windows/Linux/macOS, con importación restringida a archivos previamente detectados.
- Conservada importación por archivo para escenarios donde LightBurn está en otra PC y Marking Studio corre en Server Oficina/Linux.
- UI de Sistema actualizada para detectar/importar ajustes ya descubiertos por el área.
- Compatibilidad ampliada a `.lbmt`, `.lbprefs` y `prefs.ini` sin modificar LightBurn ni el controlador.
- QA ampliado para catálogo de materiales, teléfonos, rutas multiplataforma y seguridad de discovery local.
- Documentación ampliada sobre presets, materiales, teléfonos ensamblados, seguridad, portabilidad e interoperabilidad.

## 0.3.0 — 2026-09-12

- Añadido asistente de prefijo/sufijo por campo y distinción manual vs importación.
- INOVA permite escribir `525499` manualmente y resolver `Q00525499`; CSV se conserva as-is por defecto.
- Añadido `machine_bridge.py` para importación segura de `.clb`, `.lbset`, `.lbrn/.lbrn2`, `.lbzip/.zip` y dumps GRBL.
- Añadida lectura GRBL opcional limitada a `$I` y `$$`; sin movimientos, potencia, homing ni escrituras de settings.
- Añadidos SHA-256, copia local de exports de configuración e histórico de capturas/presets.
- Presets importados pueden asociarse a un lote y quedan registrados en `job.json`.
- Diagnóstico no destructivo de límites `$130/$131` y `$32` frente al perfil configurado.
- Añadidos launchers macOS y comprobación de Python >=3.12 en Linux/macOS/Windows.
- Añadida matriz CI Windows/Linux/macOS × Python 3.12/3.13.
- Añadidas pruebas de parsers, prefijos, API, preset/material y serial read-only.
- Añadido simulador PTY GRBL de extremo a extremo para Linux/POSIX.
- Documentación ampliada: problema/propuesta, captura de ajustes del taller, interoperabilidad y matriz de compatibilidad.
- Incluido render conceptual de la solución en `docs/media/`.

## 0.2.0 — 2026-09-11

- Plantillas INOVA/Sercel/teléfono/genérico.
- CSV, series, jigs, conciliación física, histórico y verificación de escaneo.
- Licencia standalone Ed25519 y frontera de integración con Server Oficina.
- QA de lectura digital y benchmark >1,000 registros.

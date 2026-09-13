# Server Oficina Marking Studio v0.8.0

Generador local y auditable de **marcado físico de activos** para Server Oficina. Convierte identidades provenientes de captura manual, CSV o futura BD en texto + Code 128/QR/Data Matrix, las posiciona sobre jigs/bases, exige conciliación física y entrega archivos a Sculpfun Space/LightBurn/LaserGRBL sin controlar directamente el láser.

## Problema que resuelve

Un nodo sin etiqueta puede seguir siendo reconocible si se le graba `Q00525499`, pero el texto aislado obliga a capturas/verificaciones manuales. Marking Studio mantiene la inspección visual y agrega una representación escaneable. Para INOVA se parte de **Code 128 + ID operativo visible**; Sercel inicia con Code 128 + ID; teléfonos con QR + número económico estable.

El sufijo INOVA `-xx` no se inventa. Se conserva como dato adicional cuando exista, pero el estándar operativo inicial usa el identificador realmente utilizado por la operación.

## Novedades v0.8.0

- **Modo físico de marcado a nivel de plantilla/trabajo**: `positive/negative`, alcance `codes/all`, campo `islands/template`, margen y compensación de kerf medida. Los defaults conservan exactamente el flujo positivo histórico.
- El negativo ya no es sólo una propiedad puntual de un QR/barcode: puede probarse temporalmente, guardarse en una plantilla versionada y registrarse en histórico/manifiestos.
- **Preflight invariante**: siempre evalúa el símbolo positivo canónico. El SVG negativo es una instrucción de ablación, no un código que deba escanearse directamente.
- **Comparación +/−** y cupón de caracterización de cuatro paneles para validar una superficie sobre material de descarte antes de estandarizar.
- **Biblioteca de ajustes del área** ampliada con estrategia física y evidencia del lector (perfil, intentos y lecturas correctas).
- Artefactos negativos con sufijo `_NEGATIVE`, metadatos, manifiesto y aviso explícito dentro del ZIP para reducir riesgo de enviar la polaridad equivocada a máquina.
- Compensación de kerf `0` por defecto; nunca se inventa un valor. Los rectángulos compensados se unen antes del `fill-rule=evenodd` para evitar cancelaciones por solapamiento en QR/Data Matrix.
- Métrica de **área/porcentaje estimado de ablación** y advertencia cuando un negativo cubre gran parte del lienzo. No se interpreta como receta de potencia o tiempo.
- **`codes + template` se conserva como artefacto explícito de DOS ETAPAS**: el campo de fondo/códigos y el contenido positivo quedan en capas distintas, se marca `requires_secondary_operation=true` y el archivo usa `_NEGATIVE_2PASS`. Marking Studio no ejecuta esas etapas. `all + editable` sigue rechazado porque requiere contornos.
- **Elemento imagen** en el Estudio Visual: PNG/JPG se convierten a geometría 1-bit mediante umbral o Floyd–Steinberg; SVG se sanea y se incorpora como vector. No se aceptan scripts, recursos externos ni `foreignObject`; el resultado conserva IDs/capas y avisa si invade el área/quiet zone de un código.
- La calidad física de imágenes y cualquier modo invertido siguen como **PENDIENTE DE ACEPTACIÓN FÍSICA**; no se confunden con el preflight de códigos.

Documentación específica: `docs/POLARITY_AND_PHYSICAL_MARKING.md`, `docs/PRE_V080_BASELINE.md` y `docs/POST_V080_REPORT.md`.

Suite v0.8.0 final: **196 pruebas automatizadas recolectadas**. El resultado final verificado se registra en `docs/TEST_REPORT.md` y `FINAL_VERIFICATION.json`; no se declara PASS físico de láser/material/lector.

## Novedades v0.7.1

- **Grabado negativo de fondo/relieve por elemento de código**: Code 128, Code 39, QR y Data Matrix pueden conservar el modo normal o generar el complemento vectorial dentro de su caja física. El objetivo es permitir pruebas donde se rebaja el fondo y luego se frota marcador/pintura sobre las barras/módulos elevados.
- El modo negativo es **opt-in** y no cambia las plantillas existentes. El preflight conserva la validación geométrica pero marca que la aceptación física es obligatoria; no se presume soporte de polaridad inversa en el Steren COM-597.
- Corregida documentación residual que todavía repetía el falso positivo original de CairoSVG.
- `TEST_REPORT.md` consolidado para que el estado vigente no se mezcle con la matriz histórica de 0.6.2.

## Novedades v0.7.0

- **SVG saneado estructuralmente**: capas semánticas (`layer_codes`, `layer_text`, …),
  identificadores legibles y estables por elemento (`barcode_serial`) y **unicidad
  garantizada** incluso en lotes, donde cada posición recibe su propio espacio de
  nombres (`mark_0001__barcode_serial`). Corrige un defecto real de 0.6.2 en el que un
  lote de 12 marcas emitía 36 identificadores duplicados.
- **Geometría plana en milímetros**: los símbolos se emiten como `<path>` en coordenadas
  absolutas del lienzo, sin `<svg>` anidado ni `clipPath`, de modo que las medidas del
  archivo coinciden con las del diseñador.
- **Dos modalidades de exportación**: maestro editable (texto como texto, capas de
  Inkscape) y producción.
- **Importación XLSX** con selector de hoja: nunca se asume la primera. Detección de
  formato por firma de archivo, encabezados duplicados desambiguados y conversión de
  identificadores numéricos sin decimal.
- **Transformaciones declarativas**: `lowercase`, relleno con ceros (recupera el `00184`
  que Excel pierde) y campos derivados por composición simple `{serial}-{economico}`.
- **Estudio visual**: rotación por elemento, quiet zone por elemento, deshacer/rehacer,
  imantado desactivable, alineación y distribución con selección múltiple.
- **Mapeo interactivo** con resaltado cruzado entre panel, tabla de datos y lienzo, y
  navegación de registros (primero / anterior / siguiente / último / aleatorio).
- **Salida unificada**: agrupación (jig / individual / ambos) y tipo de SVG se eligen por
  separado; patrón libre de nombre de archivo.
- **Suite de pruebas v0.7.0: 59 → 151.**

## Novedades v0.6.2

- **preflight de legibilidad** en Generador y Estudio visual: evalúa geometría, compatibilidad con el lector seleccionado y degradaciones digitales antes de exportar;
- clasificación visible **ROBUSTO / ACEPTABLE / FRÁGIL / NO LEGIBLE** por cada QR/barcode;
- prueba opcional de decodificación con `pyzbar` sobre original, reducciones 75/50 %, blur, contraste, rotación y abrasión fina;
- el lienzo del diseñador queda rotulado explícitamente como **NO escaneable** y la Vista real SVG como **ESCANEABLE**, evitando confundir el placeholder de edición con el código productivo;
- selector de lector objetivo sin hardcodeo: se alimenta del catálogo de perfiles y recuerda la selección local del operador;
- advertencias automáticas si un módulo QR/Code128/Code39/Data Matrix se reduce por debajo del perfil conservador;
- recordatorio operativo permanente: importar/grabar SVG a **tamaño físico 100 %**, sin reescalado de impresora/maquetador;
- evidencia de campo inicial documentada: en una fotografía de la hoja impresa se recuperaron `TEL-0037` (QR) y `4281847` (Code 128); los códigos más pequeños/fotografiados quedan pendientes de confirmación con el Steren físico.

## Novedades v0.6.1

- navegación por tareas con portada de acciones frecuentes y separación Operación / Diseño / Control;
- modo guiado oculta el área técnica Sistema;
- preview individual en vivo, stepper de lotes y lista de capas en el diseñador;
- comentarios `WHY:` y guía de revisión para explicar por qué existe cada responsabilidad antes de modificarla;

- **Estudio visual de marcado**: crea, duplica y edita plantillas con clic o arrastrando directamente texto/serie, Code 128, Code 39, QR, Data Matrix, rectángulos y líneas; la vista real se recalcula con el mismo motor de producción.
- CSV flexible: encabezados automáticos/forzados/sin encabezado, listas de una sola columna y mapeo de campos sin depender de nombres rígidos.
- Exportación masiva de un SVG por fila (hasta 10 000 por solicitud), además del lote colocado sobre jig.
- Identidad principal, alias CSV, prefijos/sufijos y posiciones viven en la plantilla, no en ramas hardcodeadas del frontend.
- **Modo Guiado / Experto** para que un operador ocasional vea sólo el flujo esencial y un técnico pueda acceder a calibración, JSON, archivos de configuración y diagnóstico.
- asistente de prefijo/sufijo: captura manual `525499` + prefijo `Q00` → `Q00525499`; CSV permanece **as-is** por defecto;
- calibración de jigs con puntos `P0`, `PX`, `PY`, SVG `CALIBRATION ONLY` y evaluación de traslación/escala/escuadra;
- corrección de referencia de foco: el manual oficial **SCULPFUN S9 Pro** revisado indica **50 mm** bajo el borde inferior del módulo usando su columna de 50 mm;
- handoff documentado a **Sculpfun Space**, además de LightBurn/LaserGRBL;
- captura manual de los ajustes que el área ya sabe que funcionan;
- detección/importación read-only de ajustes LightBurn (`.clb`, `.lbmt`, `.lbset`, `.lbrn2`, `.lbprefs`, `.lbzip`) y LaserGRBL (`.psh`);
- biblioteca de materiales y superficies de teléfonos con jerarquía: ajuste local validado → fabricante → investigación → Material Test;
- perfiles iniciales CUBOT KingKong 9, UMIDIGI BISON X10/X10 Pro y ejemplos Xiaomi/Redmi, sin inventar un “preset universal de teléfono”;
- política segura de materiales de composición desconocida;
- simulación de lectura y SVG, lote 3×4, escalabilidad >1000 registros, GRBL read-only `$I/$$`;
- documentación de arquitectura, interoperabilidad, calibración, pruebas y **manual rápido**.

## Instalación

### Windows

`install_windows.bat` y luego `run_windows.bat`.

### Linux

`./install_linux.sh` y luego `./run_linux.sh`.

### macOS

`./install_macos.sh` y luego `./run_macos.sh`.

Requiere Python 3.12+. La UI abre en `http://127.0.0.1:8787` y FastAPI expone OpenAPI en `/docs`.

El preflight digital de lectura usa `pyzbar`. En Windows normalmente queda disponible con la instalación Python; en Debian/Ubuntu puede requerir `sudo apt install libzbar0` y en macOS `brew install zbar`. Si falta la librería nativa, Marking Studio sigue funcionando y muestra análisis geométrico/lector, pero declara que la decodificación de estrés no está disponible.

## Flujo operativo

```text
BD / CSV / manual
   ↓
reglas de captura (prefijo/sufijo)
   ↓
plantilla versionada
   ↓
CSV ↔ posición ↔ ID escrito físicamente
   ↓
calibración/origen + preset local probado
   ↓
SVG/PNG + manifiesto
   ↓
Sculpfun Space / LightBurn / LaserGRBL
   ↓
SCULPFUN / futura grabadora
   ↓
escaneo post-grabado
   ↓
histórico / futura sincronización Server Oficina
```

Una discrepancia entre el ID físico de la posición y la fila del CSV bloquea la exportación.

## Ajustes que ya usa el taller

La prioridad del programa es **no recalibrar desde cero lo que ya funciona**. Puede:

- capturar manualmente velocidad/potencia/pasadas/intervalo/foco/modo;
- importar Material Library y Material Test de LightBurn;
- importar base `.psh` de LaserGRBL en Windows;
- leer `$I/$$` del GRBL cuando el puerto esté libre;
- asociar el preset elegido al trabajo e histórico.

Nunca carga automáticamente esos valores al controlador ni dispara el láser.

## Salida

Cada lote puede incluir:

- `engraving/batch.svg` — geometría autoritativa positiva en mm; en invertido se llama `batch_NEGATIVE.svg`;
- `engraving/batch_300dpi.png` — alternativa raster;
- `preview/preview_DO_NOT_ENGRAVE.svg` — base/jig visual, separada;
- `manifest/manifest.csv` y `manifest/manifest.json`;
- `manifest/job.json` con plantilla, máquina, preset/material, licencia y auditoría.

## Escalabilidad

La base física y el dataset son independientes. 1,200 registros con una base de 12 producen 100 cargas físicas. Las pruebas también ejercitan archivos de varios miles de registros.

## Seguridad y límites

- Marking Studio no transmite trabajos de producción, movimiento ni potencia.
- El diagnóstico GRBL está limitado a `$I` y `$$`.
- El foco y el material deben validarse físicamente.
- Un rango investigado **no es un preset productivo**.
- PVC/vinilo y materiales desconocidos se bloquean/derivan a evaluación segura.
- La validación digital no sustituye el piloto real con SCULPFUN + material + lector.

## Documentación principal

Empiece por:

- `docs/MANUAL_RAPIDO.md` — operación simple;
- `docs/PROBLEM_AND_PROPOSAL.md` — problema y propósito;
- `docs/RESEARCH_AND_DESIGN.md` — investigación, decisiones y descartes;
- `docs/ARCHITECTURE.md`;
- `docs/CALIBRATION_AND_ALIGNMENT.md`;
- `docs/SOFTWARE_HANDOFF_AND_MACHINE_SETTINGS.md`;
- `docs/MACHINE_INTEROPERABILITY.md`;
- `docs/SHOP_SETTINGS_CAPTURE.md`;
- `docs/MATERIAL_PRESETS_AND_PHONE_SURFACES.md`;
- `docs/OPERATING_STANDARD.md`;
- `docs/CSV_AND_TEMPLATE_GUIDE.md`;
- `docs/VISUAL_TEMPLATE_STUDIO.md` — diseñador visual, campos y exportación masiva;
- `docs/SCAN_QUALITY_AND_FIELD_VALIDATION.md` — preflight de lectura, límites y validación física;
- `docs/NEGATIVE_ENGRAVING_AND_RELIEF.md` — grabado negativo, relieve/relleno, polaridad y aceptación física;
- `docs/POLARITY_AND_PHYSICAL_MARKING.md` — modelo físico v0.8.0: polaridad, alcance, campos, kerf, comparación y biblioteca validada;
- `docs/PRE_V080_BASELINE.md` — línea base independiente de v0.7.1 antes de la evolución física;
- `docs/POST_V080_REPORT.md` — comparación PRE/POST y aceptación de v0.8.0;
- `docs/UX_AND_WORKFLOW.md` — decisiones de interfaz y flujo para modo guiado/experto;
- `docs/CODE_REVIEW_GUIDE.md` — inventario de funciones/clases y motivo de cada responsabilidad;
- `docs/MAINTAINER_GUIDE.md` — invariantes y procedimiento para extender sin hardcodeo;
- `docs/COMPATIBILITY_MATRIX.md`;
- `docs/SERVER_OFICINA_INTEGRATION.md`;
- `docs/LICENSE_ARCHITECTURE.md`;
- `docs/TEST_REPORT.md`;
- `docs/PRE_CHANGE_BASELINE.md` — línea base medida antes de evolucionar, con su corrección registrada;
- `docs/POST_CHANGE_REPORT.md` — resultado de Claude tras la evolución 0.6.2→0.7.0;
- `docs/INDEPENDENT_REVIEW_v0.7.1.md` — auditoría independiente y extensión 0.7.1;
- `docs/DATA_INGESTION.md` — CSV/XLSX, hojas, mapeo y transformaciones;
- `docs/PRESENTATION_SUMMARY.md`.

El render conceptual está en `docs/media/marking_studio_trazabilidad_industrial_integral.png`.

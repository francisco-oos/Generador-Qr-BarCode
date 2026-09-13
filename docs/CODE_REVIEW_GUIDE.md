# Guía de revisión del código — Marking Studio v0.6.1

Esta guía es un inventario para revisores. Los comentarios `WHY:` viven también junto al código para conservar la intención cerca de la implementación. Si una función cambia de propósito, deben actualizarse ambos lugares.

## Mapa de módulos Python

- **`app/licensing.py`** — Licenciamiento desacoplado del motor de marcado.
- **`app/models.py`** — Contratos Pydantic y validación de entrada/configuración.
- **`app/barcode_engine.py`** — Geometría SVG de texto y códigos.
- **`app/material_catalog.py`** — Referencias de materiales/superficies.
- **`app/config_loader.py`** — Carga/persistencia de configuración declarativa.
- **`app/batch_engine.py`** — Asignación física de filas a jigs y render de lotes.
- **`app/calibration.py`** — Referencias P0/PX/PY y evaluación geométrica.
- **`app/template_engine.py`** — Motor autoritativo de plantillas.
- **`app/db.py`** — Auditoría SQLite local.
- **`app/machine_bridge.py`** — Importación/diagnóstico read-only de software/controladora.
- **`app/main.py`** — API FastAPI y composición de flujos.
- **`app/exporters.py`** — Artefactos PNG/SVG/manifiestos/ZIP.

## Funciones y clases Python


### `app/barcode_engine.py`

| Línea | Símbolo | Tipo | Por qué existe |
|---:|---|---|---|
| 23 | `SvgFragment` | clase | Resultado geométrico reutilizable con SVG interno y dimensiones físicas explícitas. |
| 30 | `SafeFormatDict` | clase | Permite formatear literales con campos ausentes sin romper todo el render durante diseño/preview. |
| 32 | `SafeFormatDict.__missing__` | función | Conserva el marcador faltante para hacerlo visible al diseñador en lugar de perder silenciosamente información. |
| 37 | `resolve_value` | función | Resuelve la fuente de un elemento desde datos o literal y aplica formato seguro de variables. |
| 52 | `_extract_svg_root` | función | Extrae contenido y dimensiones de un SVG generado por librerías externas para integrarlo en nuestro documento físico. |
| 60 | `_nest_svg` | función | Anida un SVG externo con transformación y tamaño controlados sin duplicar cabeceras de documento. |
| 78 | `reposition_fragment` | función | Reposiciona un fragmento ya generado; se usa para alinear elementos sin regenerar la simbología. |
| 89 | `code128_fragment` | función | Genera Code 128 vectorial porque es el estándar inicial de nodos y mantiene lectura por escáner más texto visible. |
| 110 | `code39_fragment` | función | Ofrece Code 39 para equipos/procesos heredados sin introducir lógica específica en el diseñador. |
| 131 | `qr_fragment` | función | Genera QR vectorial con tamaño de módulo físico, apropiado para activos leídos con cámaras o lectores 2D. |
| 173 | `datamatrix_fragment` | función | Genera Data Matrix compacto para piezas donde un QR resulte demasiado grande. |
| 195 | `text_fragment` | función | Genera texto vectorial posicionado en milímetros para conservar inspección visual junto al código. |

### `app/batch_engine.py`

| Línea | Símbolo | Tipo | Por qué existe |
|---:|---|---|---|
| 21 | `normalize_identifier` | función | Normaliza sólo cuando la política lo solicita; evita que comparaciones físicas fallen por formato incidental. |
| 26 | `parse_csv_text` | función | Convierte CSV/listas flexibles en filas uniformes y detecta encabezados sin imponer un esquema de empresa. |
| 74 | `slot_positions` | función | Calcula coordenadas de slots desde el jig para que la colocación en cama sea reproducible y auditable. |
| 98 | `chunk_count` | función | Calcula cuántas cargas físicas requiere un dataset sin confundir cantidad de registros con capacidad de jig. |
| 105 | `_extract_svg` | función | Separa contenido interno de una marca individual para insertarla en el SVG del lote. |
| 111 | `_nest_mark` | función | Anida una marca en su slot conservando unidades y traslación física. |
| 126 | `BatchRenderResult` | clase | Agrupa el SVG final y la información usada para manifestar cada posición. |
| 134 | `render_batch` | función | Valida asignaciones, conciliación y posiciones y construye una cama de grabado sin mezclar guías visuales con producción. |

### `app/calibration.py`

| Línea | Símbolo | Tipo | Por qué existe |
|---:|---|---|---|
| 19 | `_grid_extents` | función | Obtiene el rectángulo físico ocupado por un jig para ubicar referencias sin depender de números escritos a mano. |
| 27 | `jig_reference_points` | función | Define P0/PX/PY esperados como base mínima para detectar desplazamiento, escala y giro. |
| 44 | `calibration_target_svg` | función | Genera un patrón explícitamente separado de producción para medir el sistema sin usar activos buenos. |
| 71 | `_vector` | función | Convierte dos puntos en vector para reutilizar la misma matemática en escala y ángulo. |
| 76 | `_length` | función | Calcula longitud euclidiana de un vector durante evaluación de escala. |
| 81 | `_angle` | función | Calcula orientación de un vector para cuantificar rotación del jig/ejes. |
| 86 | `evaluate_reference_points` | función | Compara referencias medidas y esperadas y devuelve errores comprensibles sin corregir automáticamente la máquina. |

### `app/config_loader.py`

| Línea | Símbolo | Tipo | Por qué existe |
|---:|---|---|---|
| 20 | `_read_json` | función | Lee JSON UTF-8 de forma centralizada para mantener una ruta de carga consistente y testeable. |
| 26 | `load_templates` | función | Descubre plantillas desde disco para que nuevas configuraciones aparezcan sin modificar Python. |
| 36 | `load_machines` | función | Carga perfiles de máquina declarativos y separados del código de producción. |
| 46 | `load_scanners` | función | Carga capacidades de lectores para comprobaciones y documentación operativa. |
| 56 | `load_jigs` | función | Carga bases físicas configurables y sus slots/calibración. |
| 66 | `load_quality_profiles` | función | Carga criterios de legibilidad reutilizables por plantillas. |
| 75 | `save_template` | función | Persiste una plantilla validada de forma atómica y legible para revisión humana. |
| 83 | `save_jig` | función | Persiste un jig validado fuera del código para permitir calibración/reemplazo en campo. |

### `app/db.py`

| Línea | Símbolo | Tipo | Por qué existe |
|---:|---|---|---|
| 20 | `_utcnow` | función | Genera timestamps UTC homogéneos para comparar eventos entre estaciones y futura sincronización. |
| 25 | `connect` | función | Abre SQLite con filas por nombre y una única ubicación configurable para facilitar pruebas y migración. |
| 35 | `init_db` | función | Crea el esquema idempotente al arrancar para que una estación nueva pueda operar sin pasos manuales ocultos. |
| 91 | `record_job` | función | Registra trabajo y marcas antes/después de exportar para conservar quién, qué plantilla y qué posición se usó. |
| 117 | `verify_mark` | función | Marca como verificado el registro coincidente después de un escaneo exitoso, sin reescribir su identidad histórica. |
| 132 | `history` | función | Devuelve eventos recientes para auditoría operativa y diagnóstico. |
| 147 | `record_machine_capture` | función | Guarda metadatos/hash de una configuración importada para demostrar su procedencia sin modificar el original. |
| 177 | `machine_captures` | función | Lista capturas de configuración para que la UI muestre de dónde provienen los ajustes. |
| 193 | `material_presets` | función | Lista presets capturados/importados que pueden asociarse a un trabajo. |
| 208 | `material_preset_by_id` | función | Recupera un preset concreto para incluirlo de manera estable en manifiestos. |
| 222 | `record_shop_material_preset` | función | Guarda un ajuste manual del taller con estado validado/borrador y contexto de máquina/superficie. |

### `app/exporters.py`

| Línea | Símbolo | Tipo | Por qué existe |
|---:|---|---|---|
| 13 | `svg_to_png` | función | Rasteriza una marca sólo como alternativa de interoperabilidad; SVG sigue siendo la geometría autoritativa. |
| 35 | `manifest_csv_bytes` | función | Genera un manifiesto simple interoperable con Excel/otras herramientas y útil para revisión humana. |
| 46 | `build_batch_zip` | función | Empaqueta producción, preview separado y manifiestos para que una entrega de lote sea autocontenida y auditable. |
| 70 | `build_bulk_template_zip` | función | Empaqueta miles de SVG individuales con manifiesto sin requerir un jig físico. |

### `app/licensing.py`

| Línea | Símbolo | Tipo | Por qué existe |
|---:|---|---|---|
| 25 | `LicenseError` | clase | Error de dominio para distinguir una licencia inválida de fallos técnicos generales. |
| 30 | `LicenseProvider` | clase | Contrato de proveedor de licencia; existe para que el resto del sistema no dependa del origen de autorización. |
| 33 | `LicenseProvider.status` | función | Devuelve un estado uniforme de licencia que la UI y la API pueden consumir sin conocer el proveedor concreto. |
| 38 | `StandaloneFileLicenseProvider` | clase | Valida una licencia local firmada, útil durante el piloto antes de conectar Server Oficina. |
| 40 | `StandaloneFileLicenseProvider.__init__` | función | Recibe rutas de licencia y clave pública para hacer el proveedor testeable y portable entre sistemas operativos. |
| 46 | `StandaloneFileLicenseProvider._canonical` | función | Serializa el payload de forma determinista; la firma sólo es verificable si emisor y receptor firman exactamente los mismos bytes. |
| 50 | `StandaloneFileLicenseProvider.status` | función | Verifica firma, vigencia y contenido y traduce el resultado al contrato común de licencia. |
| 81 | `ServerOficinaLicenseProvider` | clase | Punto de extensión para que una futura instalación consulte autorización directamente al servidor de oficina. |
| 90 | `ServerOficinaLicenseProvider.status` | función | Expone explícitamente que el proveedor remoto aún no está conectado, evitando aparentar una autorización inexistente. |
| 100 | `get_license_provider` | función | Selecciona el proveedor configurado en un solo lugar para que cambiar la estrategia de licencia no afecte a las rutas. |

### `app/machine_bridge.py`

| Línea | Símbolo | Tipo | Por qué existe |
|---:|---|---|---|
| 34 | `_NativePosixSerial` | clase | Fallback serial POSIX mínimo para diagnóstico read-only cuando pyserial no esté disponible. |
| 42 | `_NativePosixSerial.__init__` | función | Abre/configura el puerto POSIX con timeout explícito para no bloquear indefinidamente la estación. |
| 66 | `_NativePosixSerial.__enter__` | función | Permite usar el puerto como context manager y garantizar cierre incluso ante errores. |
| 68 | `_NativePosixSerial.__exit__` | función | Cierra siempre el descriptor al salir del contexto para liberar la controladora a LightBurn/LaserGRBL. |
| 70 | `_NativePosixSerial.close` | función | Libera el descriptor nativo de forma idempotente. |
| 74 | `_NativePosixSerial.write` | función | Envía bytes exclusivamente a través de la capa que filtra los comandos seguros. |
| 76 | `_NativePosixSerial.flush` | función | Mantiene compatibilidad con la interfaz serial usada por el probe sin añadir comportamiento de máquina. |
| 78 | `_NativePosixSerial.reset_input_buffer` | función | Descarta respuesta vieja antes del diagnóstico para no atribuirla al comando actual. |
| 81 | `_NativePosixSerial.readline` | función | Lee una línea con timeout para recopilar respuestas GRBL sin dejar la UI bloqueada. |
| 99 | `_serial_context` | función | Selecciona pyserial o fallback POSIX manteniendo una interfaz común y testeable. |
| 113 | `ImportedConfiguration` | clase | Resultado normalizado de cualquier importador, con fuente, hash y presets detectados. |
| 122 | `sha256_bytes` | función | Calcula huella de origen para auditar que un ajuste proviene exactamente del archivo importado. |
| 127 | `parse_grbl_dump` | función | Interpreta parámetros $n=v sin escribirlos, permitiendo documentar la controladora existente. |
| 161 | `list_serial_devices` | función | Descubre puertos candidatos; no abre ni opera ninguno hasta acción explícita del usuario. |
| 192 | `probe_grbl_readonly` | función | Consulta únicamente $I y $$, invariantes de seguridad que impiden movimiento o activación del láser. |
| 233 | `compare_grbl_to_profile` | función | Compara parámetros reales contra perfil para advertir diferencias sin corregirlas automáticamente. |
| 262 | `_value_attr` | función | Lee atributos heterogéneos de objetos LightBurn de forma tolerante a versiones. |
| 270 | `_coerce` | función | Convierte valores textuales importados a tipos simples conservando lo desconocido como texto. |
| 284 | `_cut_setting_to_dict` | función | Normaliza un ajuste de corte/grabado de LightBurn a campos auditables del dominio. |
| 299 | `parse_lightburn_clb` | función | Extrae presets de una Material Library de LightBurn sin modificarla. |
| 326 | `parse_lightburn_project` | función | Inspecciona proyectos LightBurn para rescatar parámetros ya usados por el área. |
| 346 | `_walk_json` | función | Recorre estructuras JSON anidadas para localizar ajustes en variantes de formato de LightBurn. |
| 360 | `parse_lightburn_lbset` | función | Extrae preferencias/ajustes legibles de archivos de configuración LightBurn. |
| 387 | `parse_lightburn_bundle` | función | Inspecciona respaldos/ZIP de LightBurn y agrega artefactos reconocibles en modo sólo lectura. |
| 432 | `parse_lightburn_lbmt` | función | Extrae presets de Material Test para conservar pruebas que el taller ya realizó. |
| 476 | `parse_lightburn_prefs` | función | Recupera campos útiles de preferencias LightBurn sin asumir que son parámetros productivos. |
| 512 | `lightburn_pref_roots` | función | Enumera rutas conocidas por sistema operativo para descubrimiento local no destructivo. |
| 543 | `discover_lightburn_artifacts` | función | Busca artefactos candidatos y devuelve metadatos; no los importa automáticamente para mantener consentimiento explícito. |
| 607 | `import_discovered_lightburn_artifact` | función | Importa sólo un artefacto elegido previamente por el operador y conserva su hash/origen. |
| 625 | `import_configuration_bytes` | función | Despacha bytes al parser correcto por extensión/contenido y unifica su resultado. |
| 659 | `_local_tag` | función | Extrae nombre local de etiquetas XML para tolerar namespaces en LaserGRBL. |
| 664 | `parse_lasergrbl_psh` | función | Extrae biblioteca de materiales LaserGRBL como referencia reproducible. |
| 713 | `lasergrbl_roots` | función | Calcula rutas conocidas de LaserGRBL, principalmente en Windows, sin asumir que la app está instalada. |
| 729 | `discover_lasergrbl_artifacts` | función | Busca bases de materiales y devuelve candidatos para selección humana. |
| 749 | `import_discovered_lasergrbl_artifact` | función | Importa la base LaserGRBL seleccionada manteniendo el mismo contrato de procedencia/hashes. |

### `app/main.py`

| Línea | Símbolo | Tipo | Por qué existe |
|---:|---|---|---|
| 85 | `lifespan` | función | Inicializa almacenamiento y recursos una sola vez al arrancar/cerrar la aplicación. |
| 100 | `_license_status` | función | Centraliza lectura de licencia para no repetir lógica de autorización en cada ruta. |
| 105 | `_require_license` | función | Bloquea rutas operativas cuando la autorización no es válida, antes de ejecutar lógica o escribir histórico. |
| 114 | `index` | función | Sirve la interfaz local desde el mismo proceso para simplificar instalación en Windows/Linux/macOS. |
| 120 | `health` | función | Expone versión, capacidades y límites de seguridad para diagnóstico/automatización. |
| 139 | `license_status` | función | Permite a la UI mostrar estado de licencia sin acceder directamente a archivos de firma. |
| 145 | `catalog` | función | Entrega plantillas, jigs, máquinas, lectores y calidad desde configuración, evitando catálogos duplicados en JavaScript. |
| 168 | `render` | función | Renderiza una marca individual usando la ruta autoritativa del template engine. |
| 203 | `csv_inspect` | función | Analiza CSV/listas y devuelve columnas/filas para que el usuario mapee datos sin formato rígido. |
| 231 | `series_generate` | función | Genera secuencias explícitas y limitadas cuando la regla de numeración es conocida. |
| 253 | `batch_export` | función | Valida un lote, renderiza el jig, registra auditoría y entrega un ZIP listo para handoff. |
| 332 | `scan_verify` | función | Compara lectura real con identidad esperada y registra verificación sólo si coincide. |
| 345 | `get_history` | función | Expone histórico reciente sin dar acceso directo a SQLite. |
| 354 | `preview_template_api` | función | Previsualiza un borrador no guardado con el mismo motor usado en producción. |
| 376 | `bulk_svg_export` | función | Genera un SVG por fila para lotes sin jig, manteniendo nombres y manifiesto deterministas. |
| 387 | `bulk_svg_export.safe_name` | función | Aísla safe_name para que el flujo sea testeable, mantenible y fácil de auditar. |
| 429 | `save_template_api` | función | Valida y guarda plantillas del estudio visual como datos configurables. |
| 437 | `template_input_rule` | función | Actualiza una regla de captura específica sin obligar al frontend a reescribir a ciegas el archivo entero. |
| 460 | `save_jig_api` | función | Valida y guarda bases físicas configurables desde modo experto. |
| 472 | `materials_reference` | función | Consulta la biblioteca de referencia y conserva sus advertencias/política de seguridad. |
| 479 | `materials_phone` | función | Devuelve conocimiento de superficie por modelo sin inventar material cuando no está confirmado. |
| 495 | `machine_ports` | función | Lista puertos seriales para diagnóstico explícito, sin abrirlos ni transmitir comandos. |
| 502 | `machine_lightburn_discover` | función | Descubre artefactos LightBurn locales en modo lectura para rescatar conocimiento del taller. |
| 514 | `machine_lightburn_import_local` | función | Importa un artefacto previamente seleccionado y registra su procedencia/presets. |
| 548 | `machine_parse_grbl` | función | Interpreta texto GRBL pegado/subido sin necesidad de conectar la grabadora. |
| 555 | `machine_probe_grbl` | función | Ejecuta el probe read-only limitado a $I/$$ y registra la captura. |
| 584 | `machine_import` | función | Importa configuraciones subidas de LightBurn/LaserGRBL/GRBL a través del parser unificado. |
| 631 | `machine_capture_history` | función | Devuelve capturas y presets para selección/auditoría en la UI. |
| 644 | `calibration_jig` | función | Genera referencias/archivo de calibración de un jig sin mezclarlas con grabado productivo. |
| 668 | `calibration_evaluate` | función | Evalúa mediciones de P0/PX/PY y devuelve errores geométricos para decisión humana. |
| 686 | `save_shop_material_preset` | función | Guarda un ajuste del área y sólo lo marca validado si el operador confirma misma máquina/superficie. |
| 706 | `machine_lasergrbl_discover` | función | Descubre bibliotecas LaserGRBL locales sin importarlas ni cambiarlas. |
| 715 | `machine_lasergrbl_import_local` | función | Importa una biblioteca LaserGRBL seleccionada en modo sólo lectura y registra sus presets. |

### `app/material_catalog.py`

| Línea | Símbolo | Tipo | Por qué existe |
|---:|---|---|---|
| 18 | `load_material_reference` | función | Carga una única fuente versionada de referencias para evitar duplicar recomendaciones en frontend y backend. |
| 30 | `search_material_reference` | función | Filtra la referencia por texto/categoría manteniendo siempre las advertencias de seguridad asociadas. |
| 53 | `phone_reference` | función | Busca marca/modelo y devuelve superficies conocidas sin convertir el nombre comercial en una suposición de material. |

### `app/models.py`

| Línea | Símbolo | Tipo | Por qué existe |
|---:|---|---|---|
| 19 | `InputRule` | clase | Regla declarativa de captura por campo, incluido prefijo/sufijo manual y política para valores importados. |
| 39 | `InputRule.input_field_safe` | función | Normaliza y valida el nombre del campo para impedir reglas ambiguas o claves peligrosas. |
| 48 | `ElementSpec` | clase | Describe un objeto visual de plantilla con geometría, fuente de datos y propiedades específicas de cada simbología. |
| 65 | `ElementSpec.validate_content_source` | función | Exige que un elemento de contenido tenga una fuente o literal coherente, evitando SVG vacíos difíciles de detectar. |
| 73 | `TemplateSpec` | clase | Contrato completo de una plantilla visual versionada y libre de dependencias de una grabadora concreta. |
| 91 | `TemplateSpec.id_safe` | función | Restringe el identificador de plantilla a un formato estable apto para archivos, API y referencias históricas. |
| 99 | `QualityProfile` | clase | Límites de legibilidad y robustez reutilizables por distintas plantillas. |
| 114 | `MachineProfile` | clase | Describe capacidades de una grabadora/controlador sin conceder permiso para operarla directamente. |
| 131 | `ScannerProfile` | clase | Describe simbologías y restricciones conocidas de un lector para validar compatibilidad de diseño. |
| 144 | `JigGrid` | clase | Geometría repetitiva de una base física usada para calcular posiciones. |
| 158 | `JigProfile` | clase | Define una base/jig, su capacidad y sus referencias de calibración. |
| 171 | `JigProfile.capacity` | función | Calcula capacidad efectiva desde slots habilitados para que el batch no dependa de cifras duplicadas. |
| 176 | `RenderRequest` | clase | Entrada para renderizar una marca individual con datos y modo de captura explícitos. |
| 185 | `BatchAssignment` | clase | Vincula una fila de datos con una posición física y, opcionalmente, con la identidad observada por el operador. |
| 192 | `BatchExportRequest` | clase | Contrato de exportación de un lote colocado sobre jig con trazabilidad y confirmación física. |
| 203 | `SeriesGenerateRequest` | clase | Entrada controlada para crear numeraciones conocidas sin inferir seriales perdidos. |
| 214 | `SeriesGenerateRequest.field_safe` | función | Valida el campo de salida de una serie con las mismas reglas usadas por plantillas y CSV. |
| 223 | `ScanVerifyRequest` | clase | Entrada mínima para comparar lo esperado contra lo leído después del grabado. |
| 230 | `TemplateSaveRequest` | clase | Envuelve una plantilla antes de persistirla y fuerza validación Pydantic completa. |
| 235 | `TemplatePreviewRequest` | clase | Permite previsualizar una plantilla todavía no guardada usando el mismo motor de producción. |
| 245 | `BulkTemplateExportRequest` | clase | Solicita un SVG por registro para escenarios sin jig o composición posterior en el software de la máquina. |
| 257 | `JigSaveRequest` | clase | Envuelve un jig antes de persistirlo y reutiliza la validación del modelo. |
| 262 | `LicensePayload` | clase | Datos firmados que identifican edición, vigencia y capacidades de una licencia. |
| 275 | `GrblParseRequest` | clase | Entrada textual para interpretar un dump GRBL sin abrir un puerto serial. |
| 280 | `GrblProbeRequest` | clase | Parámetros de una lectura GRBL segura y explícita. |
| 287 | `TemplateInputRuleUpdateRequest` | clase | Permite editar reglas de captura sin reemplazar manualmente todo el JSON de una plantilla. |
| 299 | `LocalArtifactImportRequest` | clase | Referencia un artefacto local previamente descubierto para importarlo de forma controlada. |
| 303 | `CalibrationPoint` | clase | Coordenada medida de una referencia física del jig. |
| 310 | `CalibrationEvaluationRequest` | clase | Agrupa las mediciones necesarias para comparar geometría esperada y real. |
| 316 | `ShopMaterialPresetRequest` | clase | Captura un ajuste que el área ya probó, junto con contexto suficiente para no reutilizarlo fuera de su superficie/máquina. |

### `app/template_engine.py`

| Línea | Símbolo | Tipo | Por qué existe |
|---:|---|---|---|
| 26 | `RenderedMark` | clase | Resultado autoritativo de una plantilla, con SVG, dimensiones, datos normalizados y advertencias. |
| 35 | `apply_input_rules` | función | Aplica prefijos/sufijos sólo según modo de captura, preservando CSV importado cuando la plantilla así lo indica. |
| 64 | `render_template` | función | Renderiza todos los elementos con una sola implementación compartida por preview, individual, batch y exportación masiva. |

## Frontend JavaScript

El frontend se mantiene sin framework para reducir dependencias en estaciones de taller. Las funciones de UI no controlan movimiento ni potencia.

| Línea | Función | Por qué existe |
|---:|---|---|
| 16 | `msg` | Añade mensajes contextuales de éxito/advertencia/error sin mezclar lógica de negocio con presentación. |
| 18 | `clear` | Limpia un contenedor antes de volver a mostrar resultados para evitar mensajes obsoletos. |
| 20 | `api` | Centraliza fetch y normaliza errores HTTP para que todos los flujos fallen de forma visible y consistente. |
| 22 | `downloadBlob` | Entrega artefactos generados al operador sin requerir acceso directo al sistema de archivos del navegador. |
| 25 | `setTab` | Cambia de área funcional y dispara sólo las cargas necesarias para mantener la interfaz rápida. |
| 40 | `sourceFields` | Deriva los campos de datos de una plantilla para que la UI no dependa de nombres hardcodeados. |
| 42 | `selectedTemplate` | Resuelve la plantilla elegida desde el catálogo autoritativo del backend. |
| 44 | `fillSelect` | Rellena selectores desde configuración dinámica y evita duplicar renderizado de catálogos. |
| 47 | `renderHomeStatus` | Resume capacidades disponibles en la portada para que el operador confirme de un vistazo que la estación cargó catálogo, máquina y lector. |
| 54 | `loadAll` | Inicializa licencia, catálogo, perfiles y vistas en un orden único y reproducible al abrir la aplicación. |
| 65 | `renderMachineCards` | Muestra capacidades de máquina para dar contexto sin convertir la UI en controlador de hardware. |
| 67 | `renderScannerCards` | Muestra simbologías del lector para que el operador sepa qué diseños puede validar físicamente. |
| 70 | `renderIndividualFields` | Construye captura manual desde los campos/reglas de la plantilla, incluida la ayuda de prefijos. |
| 79 | `scheduleIndividualPreview` | Agrupa pulsaciones rápidas antes de renderizar para ofrecer preview vivo sin saturar el backend con una petición por tecla. |
| 81 | `renderIndividual` | Renderiza la vista previa individual con el mismo motor SVG que luego se exporta. |
| 87 | `updateSeriesDefaultsFromTemplate` | Precarga serie/prefijo desde la plantilla para reducir errores de captura sin imponerlos al CSV. |
| 89 | `updateBatchJigs` | Filtra jigs compatibles por plantilla/categoría y conserva opciones genéricas cuando no hay uno específico. |
| 92 | `updateJigSummary` | Expone capacidad/calibración y dibuja los slots antes de asignar datos físicos. |
| 95 | `loadCsvFile` | Carga CSV o lista flexible y delega detección de encabezados al backend antes de mapear columnas. |
| 109 | `generateSeries` | Crea lotes secuenciales sólo bajo una regla explícita aportada por el usuario. |
| 113 | `updateBatchStepper` | Refleja el avance del flujo por lote (datos→mapeo→posiciones→salida) para orientar a usuarios que no conocen el proceso. |
| 121 | `updateBatchProgress` | Hace visible qué parte del dataset corresponde al lote físico actual. |
| 123 | `norm` | Normaliza texto únicamente para heurísticas de mapeo; no altera los valores productivos importados. |
| 125 | `bestHeader` | Sugiere la columna más probable para un campo sin impedir que el usuario corrija el mapeo. |
| 137 | `buildMapping` | Construye el mapeo plantilla↔CSV de forma dinámica, incluida la lista de una sola columna. |
| 144 | `mappedRows` | Aplica el mapeo elegido y produce filas con los nombres que espera la plantilla. |
| 146 | `renderBatchRecordPreview` | Previsualiza un registro mapeado para detectar errores antes de preparar posiciones o exportar. |
| 154 | `primaryIdentityField` | Obtiene la identidad definida por la plantilla para conciliación y nombres de archivo. |
| 156 | `candidateId` | Extrae la identidad candidata de una fila ya mapeada sin asumir fabricante o equipo. |
| 158 | `prepareBatch` | Toma la ventana actual del dataset y la coloca en slots, preservando la confirmación física. |
| 161 | `renderAssignments` | Presenta posición, esperado y observado para que el operador pueda conciliar visualmente cada pieza. |
| 177 | `deepClone` | Clona plantillas/elementos editables sin compartir referencias que provocarían cambios accidentales. |
| 179 | `safeDesignerId` | Normaliza IDs creados por el diseñador para que sean válidos como archivo, API y referencia histórica. |
| 181 | `blankDesignerTemplate` | Crea el borrador mínimo de una plantilla nueva sin imponer un tipo de equipo. |
| 186 | `designerFields` | Obtiene los campos actuales del borrador para alimentar propiedades, reglas y preview. |
| 188 | `syncDesignerHeaderToDraft` | Sincroniza metadatos visibles del formulario con el objeto de plantilla antes de renderizar/guardar. |
| 195 | `loadDesignerFromTemplate` | Abre una plantilla en el estudio visual como copia editable y prepara todos los paneles. |
| 202 | `loadConfigEditors` | Sincroniza editores visual/JSON/jig al cambiar la selección de configuración. |
| 207 | `updateDesignerJson` | Mantiene una representación JSON de auditoría del borrador sin que sea el flujo principal para principiantes. |
| 209 | `renderDesignerFields` | Dibuja variables de plantilla y ejemplos para que el usuario vea qué datos espera el diseño. |
| 221 | `loadInputRuleForm` | Carga prefijo/sufijo y política de importación del campo seleccionado. |
| 226 | `designerElementSize` | Calcula el tamaño aproximado del objeto en canvas para arrastre y límites, no como sustituto del SVG real. |
| 233 | `designerObjectLabel` | Representa cada objeto de forma reconocible en el canvas incluso antes del render SVG real. |
| 242 | `renderDesignerCanvas` | Redibuja el lienzo interactivo a escala manteniendo posiciones en milímetros. |
| 249 | `beginDesignerDrag` | Convierte movimiento del puntero a milímetros y limita el objeto a la superficie de la plantilla. |
| 255 | `renderDesignerLayerList` | Ofrece una lista de capas alternativa al canvas; facilita seleccionar objetos pequeños, solapados o difíciles de clicar. |
| 261 | `renderDesignerProperties` | Carga el elemento seleccionado en el inspector para edición precisa además del arrastre visual. |
| 269 | `applyDesignerPropertyAvailability` | Deshabilita propiedades que no aplican al tipo de elemento y evita configuraciones incoherentes. |
| 286 | `addDesignerElement` | Crea un elemento genérico con valores iniciales seguros y opcionalmente lo coloca donde se soltó. |
| 301 | `selectedDesignerElement` | Devuelve la selección actual como único punto de acceso para acciones de propiedades. |
| 303 | `updateSelectedElementFromProperties` | Aplica cambios del inspector al borrador y refresca canvas/preview en tiempo real. |
| 309 | `designerData` | Recoge datos de ejemplo usados sólo para visualizar el resultado real de la plantilla. |
| 311 | `scheduleDesignerPreview` | Agrupa cambios rápidos antes de llamar al backend y evita renders excesivos durante arrastre/escritura. |
| 313 | `renderDesignerPreview` | Solicita al backend el SVG real del borrador para que la vista final no difiera del motor productivo. |
| 319 | `refreshCatalogAfterTemplateSave` | Recarga configuración después de guardar para hacer la nueva plantilla disponible en todos los flujos. |
| 323 | `saveVisualTemplate` | Valida requisitos mínimos y persiste el borrador creado en el estudio visual. |
| 329 | `initVisualDesigner` | Conecta drag&drop, teclado y acciones del diseñador una sola vez al iniciar la UI. |
| 357 | `loadHistory` | Consulta eventos recientes para auditoría sin acceder directamente al archivo SQLite. |
| 363 | `prettySuggested` | Resume referencias de material en lenguaje operativo sin presentarlas como preset validado. |
| 376 | `materialStatusClass` | Traduce nivel de riesgo/validación a una clase visual consistente. |
| 383 | `renderMaterialItems` | Presenta referencias y advertencias de material preservando el contexto de seguridad. |
| 388 | `loadMaterialReference` | Consulta biblioteca de materiales bajo la jerarquía ajuste local > fabricante > investigación > prueba. |
| 403 | `searchPhoneReference` | Busca superficies por modelo para evitar asumir que todos los teléfonos de una marca usan el mismo material. |
| 417 | `discoverLightBurn` | Busca artefactos locales de LightBurn en modo sólo lectura antes de que el usuario elija importar alguno. |
| 438 | `loadMachineCaptures` | Carga presets/capturas ya auditados y los pone disponibles para asociarlos a trabajos. |
| 451 | `refreshPorts` | Lista puertos seriales candidatos sin abrirlos ni controlar la máquina. |
| 473 | `applyExperienceMode` | Reduce o amplía información según perfil guiado/experto sin cambiar las capacidades del motor. |
| 498 | `loadCalibration` | Genera referencias del jig y prepara datos esperados para una medición física controlada. |
| 519 | `discoverLaserGrbl` | Busca bibliotecas LaserGRBL existentes para rescatar conocimiento del taller sin modificarlo. |

## Invariantes a comprobar durante revisión

1. `template_engine.render_template` sigue siendo el renderer autoritativo para preview y producción.
2. No aparecen comandos productivos GRBL (`G0`, `G1`, `M3`, `M4`) en frontend o bridge.
3. Los datos específicos de INOVA/Sercel/teléfonos siguen en configuración/plantillas, no en ramas de lógica.
4. La importación de LightBurn/LaserGRBL permanece read-only y conserva hash/procedencia.
5. El CSV de una sola columna y el de varias columnas siguen siendo válidos.
6. Las guías/calibración nunca se mezclan con el SVG de producción.
7. Modo guiado y experto cambian visibilidad, no reglas de seguridad.

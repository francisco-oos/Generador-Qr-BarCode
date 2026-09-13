# Arquitectura de Marking Studio

## Principio central

La identidad del activo y el diseño del marcado son independientes de la grabadora. La SCULPFUN S9 Pro es el ejecutor físico actual, pero las plantillas no deben depender de ella.

```text
Activo / CSV / Server Oficina
          │
          ▼
Normalización de identidad
          │
          ▼
Template Engine
(texto / Code128 / QR / DataMatrix)
          │
          ├──────────────► SVG individual
          │
          ▼
Batch + Jig Engine
(posición, conciliación física)
          │
          ▼
SVG/PNG + manifiesto + histórico
          │
          ▼
Sculpfun Space / LightBurn / LaserGRBL
          │
          ▼
SCULPFUN / futura grabadora
          │
          ▼
Escaneo de verificación
```

## Componentes

### `barcode_engine.py`

Genera fragmentos SVG para Code 128, Code 39, QR y Data Matrix. Los tamaños se expresan en milímetros. No contiene parámetros del láser.

### `template_engine.py`

Interpreta plantillas JSON versionadas. Cada elemento tiene tipo, campo fuente, posición, tamaño y reglas de calidad.

### `batch_engine.py`

Carga filas, coloca cada marca en una posición del jig y valida el ID físico. Una discrepancia impide la exportación.

### `exporters.py`

Crea SVG, PNG y ZIP de trabajo. La geometría azul del jig sólo aparece en `preview_DO_NOT_ENGRAVE.svg`; el archivo de grabado contiene únicamente las marcas.

### `db.py`

SQLite local con trabajos y marcas. Un escaneo correcto cambia el estado del último marcado correspondiente a `verified`.

### `licensing.py`

Interfaz `LicenseProvider` con dos implementaciones:

- `StandaloneFileLicenseProvider`: licencia local firmada Ed25519.
- `ServerOficinaLicenseProvider`: límite de integración futuro.

### Frontend

Aplicación web local sin framework JS externo. Permite:

- generar marcas individuales;
- cargar CSV;
- generar series controladas;
- mapear columnas;
- asignar posiciones del jig;
- verificar el ID físico;
- exportar lotes consecutivos;
- crear/editar plantillas con un estudio visual drag-and-drop;
- previsualizar borradores sin persistirlos;
- editar plantillas/jigs JSON en modo experto;
- consultar histórico y perfiles de máquina/lector.

## Modelo de plantillas

Ejemplo conceptual:

```json
{
  "id": "inova_quantum_code128_v1",
  "width_mm": 52,
  "height_mm": 18,
  "elements": [
    {"kind":"code128","source":"manufacturer_id"},
    {"kind":"text","source":"manufacturer_id"}
  ]
}
```

Las plantillas pueden clonarse para modelos futuros sin modificar el motor.

## Modelo de jig

Un jig define filas/columnas, pitch, origen, offset de marcado y slots deshabilitados. El `inova_tray_3x4_estimate` es una aproximación inicial basada en la fotografía y debe calibrarse físicamente.

## Escalabilidad

El lote completo no se renderiza necesariamente en una sola cama física. Para 1,200 nodos y capacidad 12:

- 1 CSV con 1,200 registros;
- 100 lotes físicos;
- `Siguiente lote` incrementa el offset 12 posiciones;
- cada ZIP registra su manifiesto e histórico;
- el benchmark también renderiza 1,200 marcas vectoriales para detectar fugas/errores de escala.

Esto separa **escala de datos** de **capacidad física de la base**.

## Extensión v0.3 — captura de ajustes y transporte

### `machine_bridge.py`

Frontera explícita entre negocio y hardware. Tiene cuatro responsabilidades seguras:

1. descubrir puertos seriales;
2. leer `$I` y `$$` de GRBL bajo acción explícita del operador;
3. interpretar exports de LightBurn (`.clb`, `.lbset`, `.lbrn2`, `.lbzip`);
4. comparar valores leídos con el perfil sin escribir al controlador.

Los comandos permitidos están declarados en `SAFE_GRBL_COMMANDS = ("$I", "$$")` y cuentan con pruebas que fallan si aparece un comando de movimiento/potencia.

### Presets de material

Los presets importados se almacenan asociados a una captura (`machine_captures` → `material_presets`). Un trabajo referencia el preset por ID y copia su contenido en `job.json`. Es deliberadamente una referencia/auditoría, no una orden de modificar el controlador.

### Regla de captura manual/importada

Cada plantilla puede declarar `input_rules`. La misma identidad se trata distinto según procedencia:

```text
manual:  525499  + prefijo Q00  -> Q00525499
manual:  Q00525499              -> Q00525499 (no duplica)
CSV:     Q00525499              -> Q00525499 (as-is por defecto)
```

Esto permite un formulario cómodo sin reinterpretar datasets proporcionados por otra fuente.

### Portabilidad

FastAPI y los motores son independientes del SO. La comunicación serial usa `pyserial`; la enumeración funciona en Windows/Linux/macOS. El control de la grabadora sigue delegado al software de máquina, lo que evita ligar el core a drivers específicos.

## Extensión v0.6 — Estudio visual y datos libres

El diseñador visual es una capa de autoría sobre el mismo `TemplateSpec`. No existe un segundo formato propietario: mover un objeto modifica `x_mm/y_mm`, y la vista real llama a `render_template`. Por ello lo que el operador ve se valida con el mismo motor que produce el SVG final.

Los perfiles INOVA/Sercel/Teléfono son **datos iniciales**, no condiciones del motor. `primary_identity_field`, `csv_aliases`, prefijos, dimensiones y elementos viven en JSON.

El CSV admite tres modos de encabezado y listas sin encabezado. Si sólo existe una columna, puede alimentar automáticamente uno o varios campos de la plantilla. Con varias columnas el mapeo es explícito.

`/api/bulk/svg-export` produce un SVG individual por fila (hasta 10 000) sin G-code ni control de máquina. El flujo de producción sigue terminando en el software del láser.


## Extensión v0.7.0 — serialización del documento e ingesta

### `svg_document.py`

Único punto del sistema que escribe la cabecera `<svg>`. Ningún otro módulo puede hacerlo.

Centralizar la serialización es lo que permite **garantizar la unicidad de identificadores
con una sola prueba** en lugar de auditar cada generador por separado. `IdRegistry` reserva
identificadores y agrega un sufijo numérico si un nombre ya existe, de modo que ningún
elemento pierde su nodo.

Las capas semánticas se emiten en un orden declarado y estable (`LAYER_ORDER`), no en el
orden de inserción, para que el mismo modelo de datos produzca siempre el mismo archivo.

En lotes, `batch_engine` crea un `IdRegistry` con prefijo por posición (`mark_0001__`).
Esto hace **estructuralmente imposible** repetir un identificador entre posiciones, que es
el defecto concreto corregido en esta versión.

### `code_geometry.py` y `barcode_engine.py`

La generación de cada simbología sigue delegada en las mismas librerías que 0.6.2. Lo que
cambió es la serialización: la geometría se extrae como rectángulos milimétricos y se emite
como un único `<path>` plano en coordenadas absolutas del lienzo, sin `<svg>` anidado,
`clipPath` ni `transform="scale(1,-1)"`.

Consecuencias buscadas: ningún identificador generado por librerías externas entra al
documento, ningún recurso referenciado puede colisionar entre marcas y las coordenadas del
archivo coinciden con los milímetros del diseñador.

### `tabular.py`

Punto único de entrada de datos tabulares. Devuelve siempre la misma forma de respuesta
venga de CSV o de Excel, para que el frontend tenga un solo camino de código y el mapeo de
columnas no dependa del formato de origen. Ver `docs/DATA_INGESTION.md`.

### `raster_probe.py`

Punto único de rasterización y análisis de imagen: `RGBA → composición sobre blanco →
escala de grises → análisis`. Existe para impedir el falso positivo documentado en
`docs/PRE_CHANGE_BASELINE.md` §5.3, donde medir densidad de tinta sobre transparencia
produjo una conclusión incorrecta sobre un renderizador.

También distingue «no legible» de «no se pudo comprobar»: cuando una herramienta opcional
no está instalada devuelve `None`, y eso se reporta como NO PROBADO, nunca como PASS.

### `filenames.py`

Resolución y saneado del nombre de salida. El criterio es la intersección de las
restricciones de Windows, Linux y macOS.


## Extensión v0.7.1 — estrategia física separada de la codificación

`ElementSpec.engraving_mode` separa dos conceptos que no deben confundirse:

1. **codificación**: el contenido y patrón matemático Code128/QR/DataMatrix sigue generado por las mismas librerías;
2. **estrategia de remoción**: `positive` marca módulos/barras, `negative_background` marca su complemento dentro del área del símbolo.

La inversión se realiza después de obtener la geometría canónica, por lo que no introduce ramas INOVA/Sercel/teléfono ni reimplementa simbologías. La frontera de máquina permanece igual: el resultado es SVG y LightBurn/Sculpfun Space/LaserGRBL continúan controlando el láser.


## Extensión v0.8.0 — capa física de marcado versionada

0.8.0 generaliza el experimento `ElementSpec.engraving_mode=negative_background` de 0.7.1. Ese campo permanece únicamente para compatibilidad/migración; la fuente vigente es `TemplateSpec.marking_mode` y el override temporal del trabajo.

La cadena queda deliberadamente separada:

```text
dato → generador matemático positivo → geometría canónica → preflight positivo
                                      ↘ capa física de marcado → SVG de ablación
```

`physical_marking.py` valida combinaciones y construye campos/huecos; `code_geometry.py` contiene la unión de rectángulos necesaria para que una compensación de kerf no genere cancelaciones de paridad; `template_engine.py` aplica la estrategia después de resolver/alinear la geometría positiva; `svg_document.py` sigue siendo el único escritor del documento.

### Invariantes

- los motores Code128/Code39/QR/Data Matrix no se sustituyen;
- el preflight nunca recibe el negativo como símbolo a decodificar;
- `polarity=positive` conserva el comportamiento histórico;
- `codes+template` se representa deliberadamente como artefacto de **dos etapas**: campo/códigos en `layer_background` y contenido positivo en sus capas; el artefacto declara `requires_secondary_operation=true` y Marking Studio no ejecuta las pasadas;
- `negative/all` no admite maestro editable porque texto/strokes deben ser contornos;
- `all+template` fusiona deliberadamente la estructura por elemento y, por ahora, rechaza rotaciones;
- `kerf_compensation_mm=0` no altera la geometría; cualquier valor distinto de cero requiere medición física;
- ningún modo habilita G-code, movimiento o potencia: `direct_laser_job_streaming=false` y GRBL sigue read-only.

### Trazabilidad

El `MarkingMode` viaja en metadatos SVG, manifiesto, histórico y presets locales. Los artefactos negativos usan `_NEGATIVE` y el ZIP contiene una advertencia. Cambiar la huella física de una plantilla incrementa su versión; `validated_on` es evidencia humana y no cambia geometría.

### Biblioteca de validación

No se creó otra base. La tabla existente de presets/materiales conserva, además de parámetros de máquina, el modo físico y evidencia de lectura. Su función es recordar **qué se probó realmente**, no derivar una receta universal por material.


## Extensión v0.8.0 final — elemento imagen y operación de dos etapas

`image_element.py` es la frontera de contenido gráfico subido. PNG/JPEG se convierten a geometría 1-bit y SVG se sanea a un subconjunto vectorial antes de que `template_engine.py` cree `DocumentNode`. No se guardan enlaces externos en el SVG productivo.

El elemento `image` utiliza el mismo modelo de posición/rotación/capas que los demás objetos, pero permanece fuera de `code_quality`: una imagen no es una simbología y no debe generar un falso PASS de lectura. `template_engine.py` sólo añade una advertencia geométrica si su caja invade la caja/quiet-zone de un código.

`negative + scope=all` con imagen se rechaza hasta contar con una fusión booleana genérica probada. Esto es una limitación explícita, no una rama por fabricante.

`codes + template` se conserva porque representa uno de los cuatro experimentos físicos solicitados. Su semántica es **dos etapas** y queda visible en metadata, nombre `_NEGATIVE_2PASS`, capas y advertencias. La aplicación sigue sin transmitir parámetros ni movimiento al láser.

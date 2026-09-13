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
LightBurn / LaserGRBL
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
- editar plantillas/jigs JSON;
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

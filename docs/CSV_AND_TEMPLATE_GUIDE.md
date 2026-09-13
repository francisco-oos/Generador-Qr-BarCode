# Guía de CSV, plantillas y jigs — v0.6

## Archivos de datos

Se aceptan coma, punto y coma o tab y UTF-8 con BOM. También se admite una lista de una sola columna sin encabezado.

Ejemplo mínimo:

```text
Q00525499
Q00525500
Q00525501
```

Ejemplo estructurado:

```csv
serial,economico,modelo
Q00525499,N-184,INOVA
Q00525500,N-185,INOVA
```

El usuario elige `auto`, `con encabezado` o `sin encabezado`. Una lista sin encabezado recibe `value`; archivos multicolumna reciben `col_1`, `col_2`, etc.

## Mapeo

La aplicación no exige un nombre de columna global. Cada plantilla declara sus campos. Al cargar datos:

1. igualdad exacta por nombre;
2. alias declarados en `metadata.csv_aliases` de la propia plantilla;
3. coincidencia genérica sencilla;
4. decisión manual del usuario.

Si sólo hay una columna, se propone para todos los campos variables y el usuario puede cambiarlo.

Esto elimina tablas de sinónimos de INOVA/Sercel/teléfono dentro del código.

## Identidad para conciliación

Cada plantilla declara `metadata.primary_identity_field`. Ese campo es el que se usa preferentemente para:

- comparación `esperado ↔ escrito/escaneado`;
- nombre del SVG individual;
- lectura rápida en la tabla del jig.

Ya no existe un orden hardcodeado de `manufacturer_id`, `asset_id`, etc.

## Diseñar una plantilla

Use **Estudio visual**. El resultado sigue siendo un `TemplateSpec` JSON versionable. Los campos soportados son:

`text`, `code128`, `code39`, `qr`, `datamatrix`, `rect`, `line`.

Los elementos pueden tener `source` (campo variable) o `literal`. Un literal de texto puede usar formato, por ejemplo `ACTIVO {serial}`.

## Prefijo/sufijo

`input_rules` diferencia captura manual de importación. Ejemplo:

```text
manual 525499 + Q00 → Q00525499
CSV Q00525499        → Q00525499
```

La política importada por defecto es `as_is`.

## Exportaciones

### Jig

Genera un trabajo físico con posiciones confirmadas, SVG combinado, preview de la base y manifiestos.

### Individual masivo

Genera un SVG por fila con la misma plantilla y un manifiesto. Se utiliza cuando el acomodo final se hará después en LightBurn/Sculpfun Space u otro programa compatible.

## Jigs

Un jig sigue siendo configuración: filas/columnas, origen, pitch, tamaño de slot, offset y slots deshabilitados. Las coordenadas no están codificadas en Python.

## Versionado

No cambiar silenciosamente una plantilla aprobada si modifica payload, tamaño, simbología, posición o calidad. Crear una revisión (`*_v2`) para conservar trazabilidad histórica.

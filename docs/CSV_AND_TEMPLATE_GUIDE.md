# Guía de CSV, plantillas y jigs

## CSV

La aplicación acepta CSV con delimitador coma, punto y coma o tab, y UTF-8 con BOM (típico de Excel). La UI permite mapear columnas del archivo a los campos esperados por la plantilla.

Ejemplo INOVA:

```csv
manufacturer_id,asset_id
Q00525499,NODE-00525499
Q00503416,NODE-00503416
```

Ejemplo teléfonos:

```csv
asset_id,economic_number
PHONE-000037,TEL-0037
PHONE-000038,TEL-0038
```

## Reconciliación física

El lote no confía ciegamente en el orden del CSV. Para cada posición se solicita el ID escrito/leído en la pieza. El backend calcula el candidato en este orden:

1. `manufacturer_id`
2. `operational_id`
3. `asset_id`
4. `serial`
5. `economic_number`

Si `physical_id != candidate`, la exportación falla.

## Plantillas

Una plantilla describe una marca física. Ejemplo conceptual:

```json
{
  "id": "mi_equipo_v1",
  "width_mm": 50,
  "height_mm": 18,
  "quality_profile": "rugged_field_v1",
  "elements": [
    {
      "kind": "code128",
      "source": "manufacturer_id|asset_id",
      "x_mm": 1,
      "y_mm": 1,
      "width_mm": 48
    },
    {
      "kind": "text",
      "source": "manufacturer_id|asset_id",
      "x_mm": 25,
      "y_mm": 17,
      "font_size_mm": 4,
      "align": "center"
    }
  ]
}
```

Los campos soportados son `text`, `code128`, `code39`, `qr`, `datamatrix`, `rect`, `line`.

## Jigs

Un jig define una cuadrícula repetible sobre la cama:

- filas/columnas;
- origen X/Y;
- pitch X/Y;
- tamaño de slot;
- offset del marcado dentro de cada slot;
- slots deshabilitados.

No hay coordenadas específicas de INOVA codificadas en Python. Para otra base física sólo se crea un JSON.

## Versionado

Nunca cambiar una plantilla productiva aprobada de forma silenciosa. Crear `*_v2` si una modificación cambia:

- tamaño físico;
- payload;
- simbología;
- posición;
- módulo/quiet zone de forma relevante.

Así el histórico puede reconstruir exactamente qué se grabó.

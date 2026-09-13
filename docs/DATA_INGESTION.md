# Ingesta de datos — CSV, XLSX, mapeo y transformaciones

Versión: 0.8.0 (ingesta introducida en 0.7.0; contrato vigente)

Este documento cubre cómo entran los datos del activo a Marking Studio y qué se les hace
antes de convertirse en geometría. Es la parte del sistema donde un error produce un
archivo perfectamente válido con el identificador equivocado, así que las reglas son
explícitas y están cubiertas por pruebas.

---

## 1. Formatos aceptados

| Formato | Estado | Nota |
|---|---|---|
| `.csv`, `.txt`, `.tsv` | Soportado | Delimitador detectado automáticamente y reportado |
| `.xlsx`, `.xlsm` | Soportado | Lectura con `openpyxl` en modo read-only |
| `.xls` (heredado) | **Rechazado** | Se explica cómo convertirlo; ver decisión abajo |
| `.ods` | No soportado | No se ha presentado el caso en el área |

### Por qué se descartó `.xls`

Requiere `xlrd`, cuyo soporte del formato binario está congelado desde 2020 y cuya
superficie de parsing es mayor que la de un ZIP con XML. El usuario puede resolverlo en
diez segundos con «Guardar como» en el propio Excel o LibreOffice. Se prefirió un mensaje
accionable sobre una dependencia adicional que sólo aportaría comodidad marginal.

### Por qué `openpyxl` y no `pandas`

Sólo se necesita leer celdas. `pandas` arrastraría `numpy` y decenas de megabytes para
una tarea que se resuelve con un lector de filas. `openpyxl` es MIT, está mantenido y no
tiene dependencias nativas, lo que mantiene la instalación viable en Windows sin
herramientas de compilación.

---

## 2. Detección de formato

El formato **no** se decide por la extensión, sino por la firma del archivo:

- `PK\x03\x04` → XLSX (un XLSX es un ZIP);
- `\xd0\xcf\x11\xe0` → formato binario heredado de Excel;
- cualquier otra cosa → texto.

La razón es práctica: un adjunto renombrado a `.csv` que en realidad es un libro de Excel
es un caso frecuente, y fallar con «CSV inválido» no le dice nada al operador.

---

## 3. Hojas de Excel

**Nunca se asume la primera hoja.** Los libros reales del área empiezan a menudo con una
portada, un instructivo o una hoja de resumen, y leer esa hoja en silencio produciría un
lote vacío o, peor, un lote con datos de otra cosa.

El flujo es:

```text
1. seleccionar archivo
2. POST /api/data/sheets  →  lista de hojas
3. el operador elige la hoja
4. POST /api/csv/inspect?sheet=…  →  encabezados, filas y vista previa
```

Si el archivo es texto, el paso 2 devuelve una lista vacía y el selector no aparece.

---

## 4. Encabezados

Tres modos, idénticos para CSV y XLSX:

| Modo | Comportamiento |
|---|---|
| `auto` | Heurística conservadora |
| `yes` | La primera fila es encabezado |
| `no` | Sin encabezado; se generan `value` o `col_1`, `col_2`, … |

La heurística de `auto` trata la primera fila como encabezado sólo si no parece un dato.
Un identificador normalmente contiene dígitos; un encabezado normalmente no. **Ante la
duda se trata como dato**, porque perder el primer registro de una lista de seriales es
peor que mostrar `col_1`.

Una lista de una sola columna sin encabezado sigue siendo válida:

```text
Q00525499
Q00525500
Q00525501
```

### Encabezados duplicados

Dos columnas llamadas igual destruirían una de ellas al construir el diccionario de la
fila. Se desambiguan de forma visible: `serial`, `serial_2`.

---

## 5. Conversión de celdas de Excel a texto

Excel no distingue entre «el número 4281847» y «el identificador 4281847». Sin control
explícito, Python devolvería `4281847.0` y se grabaría un identificador inexistente que
además pasaría el preflight sin objeciones.

| Tipo en Excel | Texto resultante |
|---|---|
| `None` | `""` (cadena vacía, nunca `None`) |
| `12` | `"12"` |
| `12.0` | `"12"` |
| `12.5` | `"12.5"` |
| `True` | `"TRUE"` |
| fecha | ISO (`2026-09-12`) |

### Ceros a la izquierda

Excel convierte `00184` en el número `184` y pierde el formato. Marking Studio **no
adivina** que faltan ceros: eso sería inventar datos. En su lugar ofrece una regla
declarativa que el usuario activa a sabiendas (ver §7).

---

## 6. Mapeo de columnas

El mapeo relaciona **columna del archivo → campo de la plantilla**. El sistema propone
una coincidencia por nombre y por los `csv_aliases` definidos **dentro de la plantilla**,
nunca en el código del programa. El usuario siempre puede corregirla.

### Mapeo interactivo

Cada fila del panel muestra qué elementos de la plantilla consumen ese campo:

```text
serial      [ serial ▼ ]     barcode_serial   text_serial
economico   [ N. Econ ▼ ]    qr_activo
modelo      [ modelo ▼ ]     text_modelo
```

Un mismo campo puede alimentar varios objetos a la vez — el código de barras y el texto
legible del mismo serial — y ocultarlo es exactamente lo que hace que un mapeo equivocado
pase inadvertido.

Al enfocar un campo se resaltan simultáneamente:

- la fila del panel de mapeo;
- la columna correspondiente en la tabla de datos;
- los elementos afectados en el lienzo del diseñador.

El color del resaltado de mapeo es distinto del de selección, para que «este objeto usa
esta columna» no se confunda con «este objeto está seleccionado para moverlo».

### Navegación de registros

`Primero · Anterior · Registro N / Total · Siguiente · Último · Aleatorio`

La vista real se recalcula de inmediato con el motor de producción. El botón aleatorio
existe para detectar desbordes por longitud de dato sin revisar mil registros a mano.

---

## 7. Transformaciones declarativas

### Orden de aplicación — es parte del contrato

```text
recorte  →  caja  →  relleno con ceros  →  prefijo/sufijo  →  campos derivados
```

El orden **afecta el resultado** y por eso es fijo y documentado. Si el relleno se
aplicara después del prefijo, `Q00` + `525499` rellenado a 9 daría un identificador
distinto según el orden de las operaciones, y ese tipo de ambigüedad termina en un equipo
mal marcado.

### Reglas por campo (`input_rules`)

| Regla | Efecto |
|---|---|
| `trim` | Elimina espacios al inicio y al final |
| `uppercase` / `lowercase` | Conversión de caja; **no pueden estar ambas activas** |
| `pad_zeros_to` | Rellena con ceros a la izquierda hasta el ancho dado. `0` desactiva |
| `manual_prefix` / `manual_suffix` | Sólo en captura manual, salvo política explícita |
| `imported_values` | `as_is` (por defecto) o `ensure_prefix_suffix` |

`pad_zeros_to` **nunca recorta**: un valor más largo que el ancho se conserva completo.

### Regla de prefijos — invariante conservado

```text
manual:  525499     + prefijo Q00  →  Q00525499
manual:  Q00525499                 →  Q00525499   (no duplica)
importado: Q00525499               →  Q00525499   (as-is por defecto)
```

Un CSV que ya trae `Q00525499` jamás debe convertirse en `Q00Q00525499`. Hay pruebas que
fallan si esto se rompe.

### Campos derivados (`derived_fields`)

Composición simple por sustitución de marcadores:

```json
{"field": "etiqueta", "expression": "{serial}-{economico}", "overwrite": false}
```

- Se resuelven **después** de `input_rules`, para que usen los valores ya normalizados.
- Por defecto **no pisan** un valor que ya venía en el archivo: el archivo del área es la
  fuente autoritativa salvo decisión explícita del usuario.
- Un marcador sin resolver queda visible como `{campo}` en lugar de producir un dato
  vacío silencioso.

**Deliberadamente NO es un lenguaje de expresiones.** Sólo sustitución y texto literal.
Una calculadora dentro de la plantilla sería imposible de auditar y convertiría un
archivo de configuración en código ejecutable. Si un caso necesita más que concatenar,
corresponde resolverlo en el origen de datos.

---

## 8. Nombre de archivo

Patrón libre con los mismos marcadores:

```text
{serial}              →  Q00525499.svg
{economico}_{serial}  →  N-184_Q00525499.svg
```

El saneado apunta a la **intersección** de Windows, Linux y macOS, que es más restrictiva
que cualquiera de los tres por separado: se sustituyen los caracteres prohibidos por NTFS,
se normalizan acentos y se protegen los nombres reservados de Windows (`CON`, `PRN`,
`COM1`…). Se prefiere un nombre feo pero abrible en los tres sistemas a uno bonito que
falle al copiar la carpeta a otra máquina del área.

Los duplicados reciben un sufijo numérico en lugar de sobrescribirse.

---

## 9. Modo de salida

Dos decisiones **ortogonales**, que no deben mezclarse:

| Decisión | Opciones |
|---|---|
| Cómo agrupar los registros | jig · individual · ambos |
| Qué tipo de SVG generar | producción · maestro editable |

Mezclarlas obligaría a duplicar opciones (jig-editable, jig-producción, individual-editable…)
y a explicar una matriz en lugar de dos preguntas simples.

---

## 10. Límites conocidos

- 25 MB por archivo cargado.
- 10 000 filas por solicitud de exportación masiva. A ~9 ms por marca esto supone
  aproximadamente 90 s, por encima de lo cómodo para una petición síncrona; para
  volúmenes mayores conviene dividir el trabajo.
- La vista previa está acotada (25 filas por defecto, 500 máximo) deliberadamente: cargar
  miles de previsualizaciones en el navegador no aporta información y degrada la
  interfaz.
- `.xls` y `.ods` no se abren.

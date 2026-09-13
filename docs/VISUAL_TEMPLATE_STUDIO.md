# Estudio visual de marcado — diseño de plantillas

## Objetivo

El Estudio visual separa **la forma del marcado** de **los datos del activo**. INOVA, Sercel y Teléfono siguen disponibles como plantillas listas, pero ya no son ramas especiales del código. Un usuario puede duplicarlas o crear una nueva desde cero y guardarla como otro perfil.

La salida sigue siendo SVG/PNG. Marking Studio no sustituye LightBurn, Sculpfun Space o LaserGRBL y no transmite potencia/movimiento al láser.

## Flujo

1. Abra **Estudio visual**.
2. Seleccione una plantilla base, pulse **Duplicar**, o use **Nueva en blanco**.
3. Defina nombre, ID técnico, categoría, ancho y alto físicos en mm.
4. Añada los campos variables que necesita (`serial`, `economico`, `asset_id`, etc.).
5. Agregue elementos: texto/serie, texto fijo, Code 128, Code 39, QR, Data Matrix, rectángulo o línea.
6. Pulse un elemento para agregarlo o arrástrelo directamente desde la caja de herramientas al punto deseado del lienzo. Después puede moverlo con el mouse; para ajustes finos, use X/Y y medidas en el panel Propiedades.
7. Vincule cada elemento a un campo o use texto fijo/formato.
8. Observe la **Vista real SVG**: usa el mismo motor que la exportación de producción.
9. Configure, si hace falta, prefijo/sufijo para captura manual. El comportamiento del CSV se define aparte y por defecto permanece `as_is`.
10. Defina la **identidad principal** de la plantilla. Se usa en conciliación física y como nombre preferente en exportaciones masivas.
11. Guarde la plantilla. Aparece de inmediato en Generador y Lotes/CSV.

## Elementos y propiedades

- `text`: texto variable o literal; ancho, tamaño de fuente, alineación.
- `code128`: dato alfanumérico, ancho de caja, altura y módulo.
- `code39`: alternativa 1D para flujos compatibles.
- `qr`: dato 2D; el tamaño real depende de la cantidad de datos, el módulo y la corrección de error.
- `datamatrix`: 2D compacto; verificar compatibilidad del lector antes de estandarizar.
- `rect` y `line`: geometría auxiliar cuando forme parte real del grabado. Las guías del jig continúan separadas del archivo productivo.

El borde azul del editor es sólo una ayuda visual y no se exporta.

## Mejora de selección v0.6.1

El panel derecho incluye **Capas / elementos**. Sirve como segunda vía de selección cuando un QR, línea o elemento solapado resulte difícil de clicar en el lienzo. La capa seleccionada y el objeto del canvas representan la misma entrada de `elements`; no existe una copia visual separada.

## CSV y listas simples

Un archivo puede contener muchas columnas o solamente una lista de identificadores. Al importar:

- modo `Automático`: intenta detectar encabezados;
- `Primera fila es encabezado`: fuerza encabezados;
- `Lista sin encabezado`: genera nombres genéricos (`value`, `col_1`, ...).

Si sólo hay una columna, Marking Studio la propone automáticamente para los campos variables de la plantilla. Si hay varias, intenta coincidencia por nombre y por `csv_aliases` definidos **dentro de la propia plantilla**, no en el código del programa. El usuario siempre puede cambiar el mapeo.

Esto permite tanto:

```text
Q00525499
Q00525500
Q00525501
```

como:

```csv
serial,economico,modelo
Q00525499,N-184,INOVA
Q00525500,N-185,INOVA
```

## Exportación masiva

Hay dos salidas distintas:

- **Trabajo de jig**: un SVG con las marcas colocadas para las posiciones físicas confirmadas y su manifiesto.
- **SVG individuales del CSV**: genera un SVG por fila usando exactamente la misma plantilla, útil para reacomodar posteriormente en LightBurn/Sculpfun Space o para otro proceso.

El exportador masivo admite hasta 10 000 filas por solicitud. Se probó específicamente con 1 000 y 5 000 SVG individuales.

## Datos no hardcodeados

Los datos que cambian por operación viven en configuración/plantillas:

- campos y alias CSV;
- identidad principal;
- prefijos/sufijos;
- elementos y posiciones;
- dimensiones físicas;
- calidad del símbolo;
- jigs;
- máquinas, lectores y presets.

El motor conserva únicamente lógica genérica de renderizado, validación, exportación y seguridad.

## Reglas de seguridad

El diseñador permite componer geometría; no aprueba físicamente un material. Una plantilla nueva sigue requiriendo:

**preview → Frame/origen → prueba en descarte → grabado → escaneo → aprobación**.

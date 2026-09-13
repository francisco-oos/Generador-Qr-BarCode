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
## Preflight de legibilidad v0.6.2

El lienzo central usa formas simplificadas para poder arrastrar elementos con fluidez; por ello queda marcado como **NO escaneable**. Debajo aparece la **Vista real SVG de producción**, generada por el mismo `render_template` que usa la exportación y que sí debe ser escaneable.

El botón **Probar código** toma el borrador sin guardarlo, los datos visibles y el lector objetivo seleccionado. El backend evalúa cada QR/barcode por separado:

1. resuelve el dato final después de reglas de captura;
2. calcula módulo, ancho/alto y quiet zone reales usando el generador productivo;
3. compara el módulo contra el perfil conservador de calidad;
4. verifica compatibilidad de simbología con el perfil del lector;
5. rasteriza el símbolo y, si `pyzbar/libzbar` está disponible, exige que el dato se recupere exactamente bajo una pequeña batería de degradaciones.

El objetivo es impedir que un usuario reduzca visualmente un elemento hasta que “quepa” pero pierda margen de lectura. Un PASS digital no reemplaza la aceptación física del material ni mide por sí mismo el contraste del grabado.



---

# Estudio visual v0.7.0 — manipulación

## Rotación

Cada elemento tiene `rotation_deg`, normalizada al rango 0–360, de modo que `-90` y `270`
producen exactamente el mismo archivo y dos plantillas equivalentes son comparables.

La rotación se emite como `transform="rotate(ángulo cx cy)"` sobre el `<g>` del elemento,
**no** horneada en la geometría. Esa decisión es la que permite:

- que un editor externo lea la rotación como una propiedad del objeto y no como
  coordenadas ya giradas e irreversibles;
- que la geometría del archivo siga coincidiendo con los milímetros del diseñador;
- que el ciclo «medir en Inkscape → devolver el valor a la plantilla» siga funcionando.

El centro de giro es el centro geométrico del propio elemento. Para el texto se corrige el
anclaje de línea base, ya que su caja visual arranca una altura de fuente más arriba.

Giros rápidos de 0°, 90°, 180° y 270°, más ángulo libre. Una rotación de 0° **no emite
ningún `transform`**: un transform neutro haría que un editor externo mostrara el objeto
como «transformado» sin estarlo.

Verificado que un QR rotado a 0/90/180/270 y a 45° sigue decodificando sobre el render de
producción, y que la rotación sobrevive dentro de un documento de lote.

## Quiet zone por elemento

`quiet_modules` es una propiedad del elemento de código, no un margen decorativo.

| Valor | Significado |
|---|---|
| vacío (`null`) | Hereda la quiet zone del perfil de calidad — comportamiento seguro por defecto |
| `0` | Decisión explícita del usuario; se conserva y se advierte |
| `n` | Valor concreto en módulos |

Si el valor queda por debajo de la referencia del perfil, el motor emite una advertencia y
el preflight degrada la clasificación a FRÁGIL. **No se bloquea la exportación**: hay
piezas donde físicamente no cabe el margen recomendado y el usuario experto puede decidir
continuar. Lo que no se hace nunca es ocultar el riesgo.

Referencias por simbología: Code 128 usa 10 módulos (ISO/IEC 15417), QR usa 4
(ISO/IEC 18004) y Data Matrix 1 (ISO/IEC 16022). Un perfil de calidad más exigente puede
subir esos valores.

> **Corregido en 0.7.0:** el preflight evaluaba la quiet zone del perfil en lugar de la del
> elemento. Un código con el margen recortado a mano pasaba la validación y habría fallado
> sobre la pieza, que es exactamente el escenario que el preflight existe para impedir.

## Deshacer y rehacer

El historial guarda el estado **antes** de cada operación lógica, no después de cada
píxel. Un arrastre completo es una sola entrada: al soltar el objeto, un Ctrl+Z lo devuelve
a su posición original en lugar de obligar a pulsar deshacer doscientas veces.

Ediciones consecutivas de la misma propiedad se agrupan dentro de una ventana corta, de
modo que escribir `12.5` en el campo X no genera cuatro pasos de deshacer.

Operaciones cubiertas: mover, redimensionar, agregar, borrar, duplicar, rotar, desplazar
con flechas y alinear.

El historial está acotado; una sesión larga no puede agotar memoria. Los atajos Ctrl+Z y
Ctrl+Y sólo actúan con la pestaña de diseño activa, para no deshacer cambios del diseñador
mientras el usuario escribe en otra pantalla.

## Imantado

Desactivable, con rejilla configurable. Imanta a:

- la rejilla;
- el centro del lienzo;
- los bordes y centros de los demás elementos.

El propio objeto queda excluido para que no se imante consigo mismo. Se imantan el borde
inicial, el centro y el borde final, porque alinear por centro es lo que más se necesita al
componer una etiqueta.

**La tolerancia se expresa en píxeles de pantalla, no en milímetros.** Una tolerancia fija
en mm se vuelve inusable al hacer zoom: con mucho aumento el objeto saltaría varios
milímetros visibles. Convertida desde píxeles, a más zoom menos imantado, que es lo que el
usuario espera.

Las guías de imantado son transitorias y se limpian al soltar. Nunca llegan al SVG: una
guía persistente se confundiría con geometría real de la plantilla.

## Selección múltiple, alineación y distribución

Ctrl/Shift+clic, tanto en el lienzo como en la lista de capas. El número de objetos
seleccionados se muestra siempre, porque alinear con uno solo no produce ningún efecto
visible y el usuario necesita saber por qué.

Acciones: alinear izquierda / centro horizontal / derecha y superior / centro vertical /
inferior; distribuir horizontalmente y verticalmente (requieren tres o más objetos).

**Todas operan sobre milímetros físicos.** El zoom del lienzo no cambia el resultado de
alinear, y hay una prueba que falla si aparece la escala del canvas dentro de la función de
alineación.

El cálculo usa la caja visual del elemento, con la corrección de línea base del texto: sin
ella, alinear por el borde superior dejaría el texto una altura de fuente fuera de sitio.


## Estrategia de grabado por código — v0.7.1

Code 128, Code 39, QR y Data Matrix tienen `engraving_mode`:

- `positive`: el SVG marca la geometría oscura normal;
- `negative_background`: el SVG marca el complemento dentro de la caja del símbolo y deja las barras/módulos como huecos del path de fondo.

El selector está en Propiedades. El lienzo simplificado añade `NEG`, mientras la **Vista real SVG** muestra el resultado que realmente se exportará. La opción es parte de la plantilla, no una regla por fabricante.

El modo negativo no altera los datos ni el algoritmo de codificación y no se usa para texto/líneas/rectángulos. Consulte `NEGATIVE_ENGRAVING_AND_RELIEF.md` antes del piloto físico.


## Modo físico de marcado en el Estudio — v0.8.0

El modo de grabado es una propiedad física del diseño/trabajo, no una pestaña independiente. En **Directo** la interfaz conserva la simplicidad histórica. Al elegir **Invertido** se revelan progresivamente alcance, campo, margen, kerf y `validado_sobre`.

El diseñador permite experimentar con un override sin modificar el estándar guardado. **Guardar en la plantilla** persiste la configuración y versiona la plantilla si cambia su huella física. Esta separación evita que una prueba de descarte contamine automáticamente un formato ya aprobado.

La vista comparativa usa el mismo renderer productivo:

- positivo: referencia óptica/preflight;
- negativo: geometría de ablación.

El cupón de caracterización genera cuatro estrategias sobre la misma identidad para probarlas en una sola pieza de sacrificio. No es un preset de producción.

### Restricciones visibles

- `codes + template` está disponible como **2 etapas**: el fondo/código y el contenido positivo se conservan en capas distintas; el archivo usa `_NEGATIVE_2PASS` y requiere que el operador asigne operaciones separadas en el software de máquina;
- `negative + all + editable` se rechaza;
- `all + template` con rotación se rechaza hasta que exista fusión de paths transformados demostrable;
- kerf inicia en cero y siempre muestra advertencia de validación física.

El antiguo selector `engraving_mode=negative_background` por elemento se conserva sólo para abrir plantillas de 0.7.1. Nuevas plantillas deben usar `marking_mode`.


## Elemento Imagen — v0.8.0 final

La caja de herramientas incorpora **Imagen / logo**. PNG/JPG se convierten a 1-bit por umbral o Floyd–Steinberg; SVG se sanea e incorpora como vector. El usuario puede mover, redimensionar, rotar y reemplazar el archivo como cualquier otro elemento.

La propiedad de procesamiento aparece sólo al seleccionar una imagen. El lienzo muestra un placeholder de edición, mientras que **Vista real SVG** sigue siendo la autoridad productiva. Si una imagen invade la caja/quiet-zone de un código, la vista real devuelve advertencia antes de exportar. Consulte `IMAGE_ELEMENT.md`.

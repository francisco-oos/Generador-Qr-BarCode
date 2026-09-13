# Elemento imagen — v0.8.0

## Propósito

El Estudio Visual puede incorporar una **imagen** como un elemento más de la plantilla para logos, marcas, gráficos de placas, artículos de evento u otros trabajos que no son códigos de identificación. Esta función amplía el generador sin convertirlo en editor fotográfico ni en controlador del láser.

La imagen se resuelve antes de construir el SVG productivo. El documento final no contiene rutas de archivos locales ni recursos de red.

## Formatos admitidos

- PNG
- JPG/JPEG
- SVG

El archivo se embebe en la plantilla como `data URI` para que la plantilla sea portable entre Windows, Linux y macOS. El límite actual de entrada es 3 MB; las imágenes raster se limitan además a 16 megapíxeles antes del procesamiento.

## SVG de entrada

El camino preferido para logos ya vectoriales es SVG. El importador sanea el contenido a un subconjunto deliberadamente pequeño: `g`, `path`, `rect`, `circle`, `ellipse`, `line`, `polyline` y `polygon`.

Se rechazan o no se incorporan elementos que podrían depender de software, red o recursos ambiguos, entre ellos:

- `script`;
- `foreignObject`;
- `image`;
- `use`;
- referencias externas / `href`;
- estilos con `url(...)`;
- filtros;
- texto vivo;
- DOCTYPE/ENTITY.

Los colores se normalizan a geometría negra de grabado. Si el SVG depende de fuentes o efectos, debe prepararse previamente convirtiendo esos objetos a paths en un editor vectorial.

## PNG / JPG

Un láser no reproduce gris como una impresora de tinta. Por eso el raster se convierte a geometría binaria antes de entrar al SVG:

- **Threshold**: compara cada píxel con un umbral 0–255.
- **Floyd–Steinberg**: tramado 1-bit para tonos continuos.

La conversión usa Pillow, una dependencia ya existente. No se añadió una librería nueva de vectorización. Los píxeles negros resultantes se agrupan en corridas horizontales y se serializan como `<path>` vectorial.

`image_dpi` controla la resolución de muestreo del arte, no la potencia ni la velocidad del láser. La salida se limita para evitar que una foto enorme genere millones de segmentos.

## Propiedades del elemento

`ElementSpec(kind="image")` conserva:

- `name` / ID estable;
- `x_mm`, `y_mm`;
- `width_mm`, `height_mm`;
- `rotation_deg`;
- `image_processing`;
- `image_threshold`;
- `image_dpi`;
- `image_preserve_aspect`;
- `image_source_name`.

El elemento vive por defecto en `layer_geometry` y puede moverse, redimensionarse y rotarse desde el mismo Estudio Visual que los demás objetos.

## Relación con códigos

Una imagen **no se decodifica** y no participa en el preflight de QR/barcode/Data Matrix. El preflight sigue evaluando únicamente símbolos de código.

El renderer calcula la caja física de códigos e imágenes y emite advertencia si una imagen invade el área completa del código, incluida su quiet zone. Es una advertencia de composición; la aceptación definitiva sigue dependiendo de la pieza real.

## Relación con polaridad negativa

- `polarity=negative + polarity_scope=codes`: la imagen permanece positiva; sólo se invierten los códigos.
- `polarity=negative + polarity_scope=all`: actualmente se rechaza si existe un elemento `image`.

La razón no es estética: un SVG subido puede tener geometría arbitraria y no existe todavía una operación booleana general, segura y probada que lo convierta en hueco de un campo negativo. No se añadió una dependencia de booleanos sólo para aparentar soporte.

## Seguridad

El backend vuelve a validar el contenido aunque el frontend ya limite el selector de archivos. Una plantilla manipulada fuera de la UI no puede insertar una URL o un script y hacer que Marking Studio los conserve en el SVG productivo.

El procesamiento `vector` sólo es válido para SVG. PNG/JPEG deben usar `auto`, `threshold` o `floyd_steinberg`; un SVG sólo admite `auto/vector`. El modelo lo rechaza al guardar, antes de llegar a producción.

## Aceptación física

La generación de geometría se prueba por software, pero la calidad real de un logo tramado depende de:

- material y acabado;
- tamaño del punto;
- foco;
- velocidad/potencia/pasadas;
- resolución de muestreo;
- escala física del diseño.

Por tanto la calidad de `image` está **PENDIENTE DE ACEPTACIÓN FÍSICA** hasta probar el arte sobre material de descarte con la máquina real. No se debe interpretar un SVG válido como garantía de calidad fotográfica o de durabilidad.

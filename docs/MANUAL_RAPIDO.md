# Manual rápido — Server Oficina Marking Studio 0.8.0

Pensado para un operador que conoce el equipo, pero no necesita saber programación, SVG o GRBL.

## 1. Abrir

- Windows: primera vez `install_windows.bat`; después `run_windows.bat`.
- Linux: `./install_linux.sh` y `./run_linux.sh`.
- macOS: `./install_macos.sh` y `./run_macos.sh`.

Abrir `http://127.0.0.1:8787` si el navegador no se abre solo.

## 2. Elegir una tarea

Al abrir, **Inicio** ofrece cuatro accesos directos: marcar un equipo, procesar CSV/lote, crear una plantilla o verificar un grabado. En modo guiado puede trabajar sin entrar a Sistema/JSON.

## 3. Usar una plantilla ya preparada

1. Entre a **Generador**.
2. Seleccione INOVA, Sercel, Teléfono u otra plantilla guardada.
3. Escriba los datos solicitados.
4. La vista previa cambia automáticamente mientras escribe.
5. Descargue SVG (preferido) o PNG.
6. Abra el archivo en LightBurn, Sculpfun Space o el software configurado para la máquina.
7. Use el preset ya validado por el área, verifique foco/origen y haga **Frame**.
8. Grabe y luego use **Verificar escaneo**.

Marking Studio genera el diseño; **no sustituye el software que controla la grabadora**.

## 4. Crear una plantilla visual

1. Abra **Estudio visual**.
2. Elija una plantilla base y pulse **Duplicar**, o **Nueva en blanco**.
3. Defina ancho/alto del área de marcado en milímetros.
4. Agregue campos de datos, por ejemplo `serial`, `economico` o `asset_id`.
5. Pulse un elemento: **Texto/serie, Texto fijo, Code 128, QR, Data Matrix**, etc.
6. Arrástrelo con el mouse al lugar deseado. Si queda pequeño o superpuesto, selecciónelo desde **Capas / elementos** en el panel derecho.
7. Selecciónelo y ajuste X/Y, medidas, fuente, módulo y campo origen.
8. Observe **Vista real SVG**. Ésa usa el mismo renderizador de la producción.
9. Elija la **identidad principal** para conciliación física/nombre de archivo.
10. Pulse **Guardar plantilla**.

La nueva plantilla aparece en Generador y Lotes/CSV sin modificar código.

## 5. Prefijo al capturar a mano

En Estudio visual, seleccione el campo y configure una regla. Ejemplo:

- operador escribe `525499`;
- prefijo manual `Q00`;
- resultado `Q00525499`.

Por defecto, un CSV con `Q00525499` se usa **tal cual**, para evitar `Q00Q00525499`.

## 6. Cargar CSV o una lista de puros números

En **Lotes / CSV** puede cargar:

```text
Q00525499
Q00525500
Q00525501
```

sin encabezado, o un CSV con muchas columnas.

En **Encabezados** elija:

- Detectar automáticamente;
- La primera fila es encabezado;
- Lista sin encabezado.

Si sólo existe una columna, el programa la propone automáticamente para los campos de la plantilla. Con varias columnas, muestra el mapeo y usted decide qué columna alimenta cada campo.

La vista previa del primer registro cambia en cuanto modifica el mapeo.

## 7. Trabajar con un jig/base

1. Cargue datos.
2. Elija plantilla y jig.
3. Pulse **Preparar posiciones**.
4. Coloque las piezas físicamente.
5. Capture/escanee el ID escrito en cada posición.
6. Si aparece **NO coincide**, no exporte: corrija pieza o fila.
7. Exportar trabajo ZIP.
8. Abra `engraving/batch.svg` en el software del láser.
9. Nunca grabe `preview/preview_DO_NOT_ENGRAVE.svg`.
10. Frame → grabar → verificar.

## 8. Generar muchos SVG sin jig

Después de cargar/mapear el CSV, pulse **Generar SVG individuales del CSV**. El ZIP contendrá un SVG por fila más manifiestos. Es útil si después el área quiere acomodarlos manualmente en LightBurn/Sculpfun Space.

La prueba de software ejercita 1 000 y 5 000 SVG individuales.

## 9. Lectores

- **Steren COM-597**: puede verificar Code 128, QR y Data Matrix según el perfil documentado del proyecto.
- **LS2208** (si todavía existe alguna estación): lector 1D; usar Code 128, no QR.

El código correcto es el que el lector real lee repetidamente después del grabado, no sólo el que se ve bien en pantalla.

## 10. Materiales y teléfonos

Primero reutilice el ajuste que el área ya sabe que funciona para la misma máquina/superficie. No existe un preset universal para “plástico” o “Xiaomi”. Modelo y zona importan.

Para una superficie nueva: material identificado → prueba conservadora → contraste legible → verificación con lector → guardar preset local.

## 11. Calibrar posición

Use **Calibración** con material de sacrificio. Genere P0/PX/PY, haga Frame, mida y compare. No use un activo bueno para descubrir offsets.

## 12. Regla final

Un trabajo sólo se libera cuando se cumplen las tres:

**ID correcto + grabado visible + lectura correcta.**
## 13. Probar que el QR/barcode realmente se lea antes de grabar

En **Generador** o **Estudio visual**, seleccione el lector que usará en campo y pulse **Probar legibilidad / Probar código**.

El sistema revisa:

- dato exacto que contiene el símbolo;
- módulo físico y tamaño real en milímetros;
- que el código no salga del área de la plantilla;
- que el lector seleccionado declare la simbología;
- una simulación digital con reducción, desenfoque, contraste, rotación y abrasión ligera cuando el decodificador está disponible.

Resultados:

- **ROBUSTO**: buen margen digital y geométrico;
- **ACEPTABLE**: válido, pero con menor margen;
- **FRÁGIL**: puede leer en pantalla y fallar al imprimir/grabar; aumente módulo/tamaño o mejore contraste;
- **NO LEGIBLE**: no liberar a producción.

Importante: el **Lienzo de edición NO es escaneable**. Es sólo una representación para mover objetos. La **Vista real SVG de producción sí es el código real**.

Al imprimir una prueba en papel o importar a LightBurn/Sculpfun Space, conserve **100 % del tamaño físico**. La opción “Ajustar a página” puede adelgazar las barras y convertir un código correcto en uno frágil.

La prueba definitiva sigue siendo: grabar sobre material equivalente y leer varias veces con el lector real desde distintas posiciones.



---

## Novedades de la versión 0.7.0 — guía breve

### Cargar un archivo de Excel

1. En **Lotes / CSV**, pulse *Archivo Excel / CSV / lista*.
2. Si es un libro de Excel aparecerá el selector **Hoja de Excel**. Elija la hoja que
   contiene el inventario. El programa no adivina cuál es.
3. Revise la tabla de vista previa. Debajo indica de qué hoja se leyó y cuántos registros
   hay en total.
4. Si los encabezados no se detectaron bien, cambie *Encabezados* y el archivo se vuelve a
   leer solo; no hace falta seleccionarlo otra vez.

### Recuperar ceros perdidos por Excel

Si en Excel tenía `00184` y el programa muestra `184`, el número perdió su formato al
guardarse. No lo corrija a mano fila por fila:

1. Abra la plantilla en **Estudio visual**.
2. En las reglas de captura del campo, ponga *Rellenar con ceros hasta* = `5`.
3. Todos los registros recuperan el ancho: `184` vuelve a ser `00184`.

Un valor que ya sea más largo nunca se recorta.

### Comprobar que cada dato llega al objeto correcto

En el panel de mapeo, pulse sobre un campo. Se iluminan a la vez la columna del archivo, la
fila del panel y el objeto en el lienzo. Así ve de un vistazo que `serial` alimenta el
código de barras **y** el texto legible.

Use *Primero*, *Siguiente*, *Último* y **Aleatorio** para revisar varios registros. El
aleatorio sirve para detectar datos más largos de lo normal que se salgan de la etiqueta.

### Girar un objeto

Selecciónelo y use los botones `0° 90° 180° 270°`, o escriba un ángulo. La vista real se
actualiza al instante y el giro se conserva en el archivo exportado.

### Deshacer

`Ctrl+Z` deshace y `Ctrl+Y` rehace, o use los botones de la barra. Un arrastre completo se
deshace de una sola vez.

### Colocar objetos con precisión

- Los objetos se **imantan** a la rejilla, al centro del lienzo y a los bordes de otros
  objetos. Aparece una línea rosa indicando a qué se está alineando.
- Para un ajuste milimétrico sin imantado, desmarque **Ajustar** en la barra.
- Seleccione varios objetos con `Ctrl+clic` y use los botones de alineación.

### Elegir qué archivos generar

Son dos preguntas independientes:

- **Modo de salida**: lote sobre el jig, un SVG por registro, o ambos.
- **Exportación SVG**: *Producción* (recomendada) o *Maestro editable*, que conserva el
  texto como texto para poder ajustarlo en Inkscape.

Puede definir el nombre de los archivos con un patrón como `{economico}_{serial}`.


## 16. Modo físico de marcado — directo e invertido (0.8.0)

El modo habitual sigue siendo **Directo / positivo**. Si no necesita experimentar con relieve o con una superficie que aclara al láser, no cambie nada: la pantalla conserva el flujo histórico.

Al elegir **Invertido / negativo** aparecen opciones avanzadas:

- **Alcance `codes`**: sólo QR/Code 128/Code 39/Data Matrix se invierten.
- **Alcance `all`**: también se invierten texto y geometría auxiliar; el texto se convierte a contorno.
- **Campo `islands`**: cada elemento tiene su propia isla de fondo; es la primera opción a probar porque elimina menos material.
- **Campo `template`**: usa toda la plantilla como un campo. Con `scope=all` fusiona la geometría; con `scope=codes` genera un artefacto explícito de **2 etapas**, porque el fondo/código y el contenido positivo requieren operaciones separadas.
- **Margen de campo**: amplía el área alrededor de la isla.
- **Compensación de kerf**: por defecto es `0`. Sólo introduzca un valor después de medirlo físicamente. El número representa la recuperación TOTAL del ancho; `0.10 mm` significa `0.05 mm` por lado.

El sistema identifica `codes + template` como **DOS ETAPAS** y usa `_NEGATIVE_2PASS`; Marking Studio no ejecuta ni asigna potencia/velocidad a esas etapas. Un maestro editable no se genera con `negative + all`, porque el texto debe convertirse a contornos.

### Probar sin contaminar la plantilla

En **Generador** o **Lotes / CSV**, el trabajo hereda el ajuste guardado en la plantilla. Puede cambiarlo temporalmente para experimentar. Ese cambio NO modifica el estándar guardado hasta pulsar **Guardar en la plantilla**. Si cambia la huella física (polaridad/alcance/campo/margen/kerf), la plantilla incrementa su versión.

### Comparación antes de gastar material

Use **Comparar positivo / negativo**. La izquierda es la referencia óptica esperada; la derecha es la instrucción de ablación que se enviaría al software de la máquina. No intente escanear el negativo como criterio de calidad.

También puede generar el **Cupón de caracterización** con las cuatro combinaciones invertidas del mismo dato: codes/islands, codes/template 2PASS, all/islands y all/template. El positivo se consulta en la vista comparativa. Grábelo sólo sobre material de descarte para descubrir qué estrategia merece validarse.

### Preflight

**Probar legibilidad** siempre califica el símbolo positivo canónico, aunque el archivo productivo sea negativo. Ésta es una regla deliberada: el negativo indica qué retira el láser; el lector debe recibir al final una polaridad óptica normal después de la respuesta del material o del acabado.

### Nombres y advertencias

Los archivos de producción negativos llevan `_NEGATIVE` y los ZIP incluyen una advertencia. No quite ese sufijo antes de la operación. El histórico y el manifiesto registran polaridad, alcance, campo, margen y kerf.

### Guardar evidencia física

En **Materiales / Presets**, guarde sólo lo que realmente haya probado en la misma máquina/superficie: máquina, preset, modo físico, lector, intentos, lecturas correctas y nota `validado_sobre`. Una referencia investigada no es un preset validado.

### Flujo recomendado para la primera validación

1. Use una pieza de descarte.
2. Mantenga el preset que el área ya conoce, salvo que el Material Test indique otra cosa.
3. Genere el cupón o compare dos estrategias.
4. Haga Frame en LightBurn/Sculpfun Space/LaserGRBL.
5. Grabe.
6. Si el método requiere marcador/pintura, aplíquelo y limpie el excedente.
7. Escanee al menos 5 veces con el COM-597.
8. Registre intentos/éxitos y observaciones.
9. Sólo después guarde el ajuste como validado.

**Pendiente físico:** potencia, velocidad, foco, kerf real, contraste, abrasión y comportamiento del `fill-rule=evenodd` dentro del software de máquina real no se dan por aprobados desde el software.


## 17. Agregar una imagen o logo

1. Abra **Estudio visual**.
2. Pulse **Imagen / logo** y seleccione PNG, JPG/JPEG o SVG.
3. Mueva y cambie el tamaño del elemento en el lienzo.
4. Para PNG/JPG elija **Umbral** para logos de dos tonos o **Floyd–Steinberg** para tonos continuos; ajuste el umbral/DPI sólo si entiende su efecto.
5. Para SVG use `auto/vector`; Marking Studio sanea el archivo y rechaza scripts/recursos externos.
6. Revise **Vista real SVG** y las advertencias. Si la imagen invade la quiet zone de un código, sepárela.
7. Pruebe el resultado sobre material de descarte antes de guardar un estándar físico.

Una imagen no recibe clasificación ROBUSTO/FRÁGIL porque no es un código escaneable. En negativo con alcance `codes` permanece positiva; alcance `all` con imagen se rechaza por ahora.

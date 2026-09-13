# Manual rápido — Server Oficina Marking Studio 0.6.2

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


# Manual rápido — Server Oficina Marking Studio 0.5

Este manual está pensado para alguien que **sabe identificar el equipo pero no necesita conocer programación, SVG o GRBL**.

## 1. Abrir el programa

### Windows

1. Primera vez: ejecutar `install_windows.bat`.
2. Uso diario: ejecutar `run_windows.bat`.
3. Abrir `http://127.0.0.1:8787` si el navegador no se abre solo.

### Linux

```bash
./install_linux.sh
./run_linux.sh
```

### macOS

```bash
./install_macos.sh
./run_macos.sh
```

## 2. Elegir modo

- **Guiado**: recomendado para producción diaria. Oculta configuración técnica.
- **Experto**: plantillas JSON, calibración avanzada, descubrimiento de software y diagnóstico GRBL read-only.

Cambiar de modo no cambia los datos ni el trabajo; sólo la cantidad de controles visibles.

## 3. Grabar un solo equipo

1. Ir a **Generador**.
2. Elegir plantilla: INOVA, Sercel, teléfono, etc.
3. Capturar el ID.
4. Si la plantilla pregunta **¿usar prefijo?**, elegirlo sólo para captura manual. Ejemplo: escribir `525499` y usar `Q00` produce `Q00525499`.
5. Revisar el resultado visible y el código.
6. Exportar SVG.
7. Abrirlo en Sculpfun Space o LightBurn.
8. Aplicar el preset ya probado para ese material/superficie.
9. Ajustar foco y usar **Frame**.
10. Grabar.
11. Ir a **Verificar escaneo** y comprobar que el lector devuelve exactamente el ID esperado.

## 4. Grabar varios equipos con CSV

1. Ir a **Lotes / CSV**.
2. Elegir plantilla y jig.
3. Cargar CSV.
4. Mapear la columna del identificador.
5. El valor del CSV se conserva **tal como viene** por defecto; no se agrega prefijo automáticamente salvo que la plantilla lo indique expresamente.
6. Pulsar **Preparar posiciones**.
7. Colocar las piezas en el jig.
8. Para cada posición, escribir/escanear el ID que realmente está sobre la pieza.
9. Si aparece **NO coincide**, detenerse y corregir. No exportar.
10. Cuando todo coincida, exportar el ZIP del lote.
11. Abrir `engraving/batch.svg` en el software de láser.
12. No grabar `preview/preview_DO_NOT_ENGRAVE.svg`.
13. Frame → grabar → verificar escaneos.
14. Pulsar **Siguiente lote** para continuar.

### Ejemplo de escala

Si hay 1,200 nodos y el jig acepta 12, Marking Studio prepara **100 cargas de 12**. No intenta poner 1,200 códigos en una sola cama.

## 5. Crear una serie sin CSV

Sólo para rangos que la operación ya autorizó:

1. indicar prefijo;
2. número inicial;
3. cantidad;
4. ancho con ceros;
5. sufijo opcional.

Ejemplo: `Q00` + `525499` + 3 genera:

- `Q00525499`
- `Q00525500`
- `Q00525501`

**No usar esta función para adivinar seriales de fabricante.**

## 6. Usar un ajuste que el taller ya conoce

Ir a **Materiales**.

Si el ajuste ya produce grabado visible:

- capturarlo manualmente, o
- importarlo desde LightBurn/LaserGRBL.

Guardar siempre el modelo/superficie exacta. No crear “preset Xiaomi” o “preset plástico” genérico si los materiales cambian.

## 7. Calibrar una base/jig

1. Ir a **Calibración**.
2. Elegir jig.
3. Generar referencias.
4. Descargar SVG de calibración.
5. Usar sólo material de sacrificio.
6. Abrir en software de láser.
7. Frame.
8. Marcar/medir `P0`, `PX`, `PY`.
9. En modo Experto introducir las mediciones.
10. Si el sistema reporta desplazamiento, escala o escuadra, corregir el montaje/configuración y repetir.

## 8. Enfoque de la SCULPFUN S9 Pro

El manual oficial revisado usa una **columna de 50 mm**: el foco está 50 mm bajo el borde inferior de la carcasa de aluminio del módulo láser. Seguir el manual de la unidad real y el procedimiento ya validado del área.

## 9. Qué código usar

- **INOVA**: Code 128 + ID visible (`Q00525499`).
- **Sercel con lector 1D actual**: Code 128 + ID visible.
- **Teléfono**: QR + número económico visible.
- **Equipo nuevo**: crear plantilla, probar y aprobar antes de producción.

El lector Zebra/Symbol LS2208 es 1D: no esperar que lea QR.

## 10. Si algo falla

| Problema | Qué revisar |
|---|---|
| Código se ve pero no escanea | tamaño, quiet zone, contraste, foco, orientación, lector correcto |
| Texto correcto pero barcode equivocado | payload de plantilla / columna CSV |
| Pieza equivocada en slot | conciliación física; no omitirla |
| SVG aparece con tamaño raro | importación en mm / escala en software de láser |
| Grabado demasiado tenue/fuerte | preset exacto del material; Material Test, no adivinar |
| Posición corrida | P0/origen, Frame y calibración de jig |
| No detecta LightBurn/LaserGRBL | usar importación manual del archivo de settings |
| Puerto ocupado | cerrar/desconectar el software que tenga abierto el láser |

## 11. Regla de producción

Antes de liberar un activo deben existir tres comprobaciones:

**ID correcto + grabado visible + lectura correcta.**

Cuando se integre con Server Oficina, esa verificación quedará ligada al histórico del activo.

# Manual de operación — piloto

## A. Generar una marca individual

1. Iniciar `run_windows.bat` o `run_linux.sh`.
2. Abrir `http://127.0.0.1:8787`.
3. Entrar a **Generador**.
4. Seleccionar la plantilla.
5. Capturar el identificador real del equipo.
6. Revisar la vista previa y medidas.
7. Exportar SVG para LightBurn o PNG 600 DPI como alternativa raster.
8. En LightBurn, confirmar tamaño físico y ejecutar `Frame` antes del láser.

## B. Lote desde CSV o serie controlada

1. Entrar a **Lotes / CSV**.
2. Seleccionar plantilla y jig.
3. Elegir el origen de datos:
   - **CSV**: cargar el archivo y confirmar el mapeo de columnas; o
   - **Generar serie**: definir campo, prefijo, valor inicial, cantidad, ancho con ceros y sufijo opcional. Esta función es para series conocidas/autorizadas; no debe usarse para reconstruir seriales de fabricante que no estén documentados.
4. Indicar el inicio del lote. Si el jig tiene 12 posiciones, un conjunto de 1,200 registros se procesa en 100 cargas físicas, no en una cama imposible.
5. Pulsar **Preparar posiciones**.
6. Colocar cada equipo en la posición mostrada.
7. En la columna **ID escrito / leído físicamente**, teclear o escanear el ID que realmente está en esa pieza.
8. No continuar si aparece **NO coincide**.
9. Exportar el trabajo ZIP.
10. Tras terminar físicamente esa carga, usar **Siguiente lote** para avanzar exactamente la capacidad del jig y preparar la siguiente carga.

Antes de iniciar una corrida grande, revisar en pantalla el primer y último ID del rango y conservar el CSV/manifiesto autorizado como fuente de verdad.

El botón **Simulación: prellenar confirmaciones** existe sólo para demostración/QA. No debe utilizarse como sustituto de la verificación física en producción.

## C. Archivos del ZIP

Usar para grabar:

- `engraving/batch.svg` — recomendado con LightBurn.
- `engraving/batch_300dpi.png` — fallback LaserGRBL.

No grabar:

- `preview/preview_DO_NOT_ENGRAVE.svg` — contiene rectángulos/guías del jig.

Consultar para auditoría:

- `manifest/manifest.csv`
- `manifest/manifest.json`
- `manifest/job.json`

## D. Verificación posterior

1. Después de grabar, abrir **Verificar escaneo**.
2. Capturar el ID esperado.
3. Poner el cursor en **Escaneado**.
4. Disparar el lector USB.
5. Si dice **COINCIDE**, el histórico local se actualiza.
6. Si dice **NO COINCIDE**, no liberar el activo; revisar plantilla/grabado/pieza.

## E. Crear un estándar nuevo

No modificar el motor Python para un equipo nuevo.

1. Duplicar una plantilla JSON similar en `config/templates/`.
2. Cambiar ID/version, medidas, fuentes y elementos.
3. Crear/duplicar un jig en `config/jigs/` si el equipo usa una base física diferente.
4. Mantener `calibration_required=true`.
5. Ejecutar pruebas de software.
6. Ejecutar el plan de aceptación física.
7. Una vez aprobado, versionar el estándar y conservar la versión anterior para histórico.

## F. Estándares iniciales

### INOVA Quantum

- texto humano: `Q00...` real conocido;
- Code 128: exactamente el mismo ID;
- no agregar `-xx` si no está documentado;
- plantilla: `inova_quantum_code128_v1`.

### Sercel

- para el lector 1D actual: Code 128 + ID visible;
- Data Matrix sólo cuando exista lector 2D/validación de payload;
- medir carcasa/base real antes de aprobar jig.

### Teléfonos

- QR: `asset_id` estable;
- texto: número económico;
- no codificar responsable, unidad, proyecto o ubicación mutable;
- validar el material/placa antes de grabar directamente una carcasa.

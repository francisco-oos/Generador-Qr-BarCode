# Calibración, alineación y puntos de referencia

Fecha: 2026-09-12  
Aplicación: Server Oficina Marking Studio 0.6.2

## Objetivo

La calibración de Marking Studio no pretende sustituir la calibración mecánica/electrónica del láser. Su objetivo es hacer **repetible la relación entre el archivo generado, el jig físico y la pieza real**, reduciendo el riesgo de grabar un código fuera de zona o sobre el activo equivocado.

## Tres puntos de referencia

Cada jig puede generar un SVG de calibración con:

- `P0`: origen físico del jig;
- `PX`: punto de control hacia el extremo X;
- `PY`: punto de control hacia el extremo Y.

Con esos tres puntos se pueden detectar cuatro clases de problema:

1. **traslación**: el jig está desplazado;
2. **escala X/Y**: distancia configurada y medida no coinciden;
3. **rotación**: el eje X del jig no queda paralelo al eje X esperado;
4. **escuadra**: X y Y no conservan aproximadamente 90°.

El sistema informa las diferencias, pero **no aplica correcciones automáticas** ni escribe pasos/mm.

## Procedimiento recomendado para crear un jig productivo

1. Colocar una hoja o placa de sacrificio en la cama.
2. Instalar/fijar el jig como se usará en producción.
3. En Marking Studio, abrir **Calibración**, seleccionar el jig y descargar `CALIBRATION ONLY`.
4. Abrir el SVG en Sculpfun Space o LightBurn.
5. Confirmar que el tamaño físico se mantuvo en milímetros.
6. Establecer el origen de trabajo repetible.
7. Usar **Frame** antes de marcar.
8. Marcar sólo sobre material de sacrificio, nunca sobre equipo productivo durante la calibración.
9. Medir P0, PX y PY con la mejor herramienta disponible (regla de precisión/calibrador cuando sea viable).
10. Introducir las mediciones en el evaluador experto.
11. Corregir físicamente el jig o su configuración y repetir.
12. Una vez estable, versionar el jig y registrar evidencia/fotos/medidas.

## Origen de trabajo

LightBurn documenta tres modos: `Current Position`, `User Origin` y `Absolute Coordinates`.

Para la instalación inicial de una S9 Pro abierta se recomienda **jig fijo + Current Position/User Origin + Frame**, salvo que el taller confirme y pruebe homing/limit switches y origen absoluto repetible. Absolute Coordinates no debe suponerse confiable sólo porque aparece en el software.

Referencias:

- https://docs.lightburnsoftware.com/2.0/Reference/CoordinatesOrigin/
- https://docs.lightburnsoftware.com/latest/GetStarted/FirstMaterialTest/

## Enfoque de la S9 Pro

El manual oficial S9 Pro enlazado por SCULPFUN establece:

- focal fija;
- punto de foco a **50 mm debajo del borde inferior de la carcasa de aluminio del módulo**;
- columna de medición de **50 mm** incluida para ajustar la altura.

Fuente: https://www.sculpfun.com/pages/download-center → `SCULPFUN S9 Pro User Manual`, páginas de enfoque.

Por tanto:

1. colocar la columna de 50 mm sobre la superficie que se va a marcar;
2. aflojar el tornillo del módulo;
3. bajar el módulo hasta apoyar correctamente sobre la columna;
4. apretar;
5. retirar la columna;
6. ejecutar Frame/previsualización antes de producir.

Si el taller ya usa otro espaciador por una modificación física documentada, registrarlo como configuración local; no cambiarlo por una cifra obtenida de otra versión de máquina.

## Material Test

LightBurn permite variar velocidad, potencia, intervalo y pasadas mediante Material Test y ofrece Preview/Frame antes de iniciar. SCULPFUN también recomienda pruebas por material porque no existen parámetros universales.

La regla de Marking Studio es:

> **preset local probado en la misma máquina/superficie primero; Material Test después cuando haga falta optimizar o validar otra superficie.**

## Tolerancias del evaluador

Los umbrales implementados (`0.5 mm` traslación, `0.2 %` escala, `0.3°` de escuadra/rotación) son **guías de diagnóstico del software**, no una norma industrial ni una aceptación automática. Para un código pequeño puede requerirse una tolerancia más estricta. La aceptación final se define durante el piloto físico.

## Calibración por familia

- **INOVA**: medir posición útil real sobre carcasa y pitch del cajón/base antes de aprobar `inova_tray_3x4_estimate`.
- **Sercel**: medir la zona segura en la carcasa exacta y comprobar que los tornillos/relieves no interfieran.
- **Teléfonos**: un jig debe sujetar sin presionar botones, cámara, tapa o pantalla; separar por formato físico cuando los modelos difieran.
- **Placas de activo**: pueden usar un jig dedicado de varias posiciones y suelen ser la ruta más controlable cuando la superficie del teléfono es incierta.

## Evidencia mínima de una calibración aprobada

- ID y revisión de jig;
- máquina física;
- fecha/operador;
- P0/PX/PY esperados y medidos;
- modo de origen usado;
- método de foco;
- archivo `CALIBRATION ONLY`;
- foto del montaje;
- observaciones de repetibilidad;
- decisión: borrador / aprobado / retirado.

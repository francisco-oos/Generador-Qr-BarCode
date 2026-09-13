# Estándar operativo de marcado físico

Estado: propuesta para prueba piloto. Ninguna plantilla marcada `calibration_required=true` debe considerarse productiva hasta superar validación física.

## A. Alta y preparación

1. Registrar o importar el activo.
2. Determinar el identificador que realmente usa la operación.
3. Escribir temporalmente el ID en el equipo si el flujo lo requiere.
4. El activo queda `PENDIENTE_GRABADO` en la futura integración con Server Oficina.
5. Seleccionar plantilla y jig correctos.

## B. Conciliación antes del láser

Para cada posición física del jig:

1. el sistema muestra el ID esperado del CSV;
2. el operador escribe o escanea el ID que ve físicamente;
3. sólo si ambos coinciden se habilita la exportación;
4. una discrepancia obliga a revisar posición, equipo o archivo.

Este control es el que evita grabar el serial correcto sobre el nodo equivocado.

## C. Handoff al software de máquina

1. Abrir `engraving/batch.svg` en **Sculpfun Space o LightBurn** (LaserGRBL queda como alternativa según su flujo).
2. Confirmar dimensiones físicas en mm.
3. Aplicar el preset ya validado para la combinación exacta máquina + superficie.
4. Confirmar foco. En la S9 Pro revisada, el manual oficial usa la columna de **50 mm**.
5. Ejecutar `Preview`/`Frame`.
6. Confirmar que el código cae en la zona aprobada del equipo y que P0/origen son correctos.
7. Ejecutar prueba sobre carcasa/muestra de descarte si el perfil aún no está aprobado.
8. No grabar las guías del jig; sólo están en el archivo de preview.

## D. Aprobación de material

Por cada combinación **máquina + material/carcasa + plantilla** registrar:

- fecha;
- modelo de equipo;
- lote/material si aplica;
- enfoque/altura según manual;
- velocidad;
- potencia;
- pasadas;
- air assist si aplica;
- resultado visual;
- lectura del LS2208/lector real;
- fotos y observaciones.

Usar Material Test de LightBurn para determinar parámetros. No copiar parámetros de otro plástico o carcasa sin prueba.

## E. Verificación posterior

Después de grabar:

1. inspección visual: texto completo y sin daño estructural;
2. escaneo del código;
3. comparar dato escaneado con el esperado;
4. sólo un match exacto cambia el marcado a `VERIFICADO`;
5. si falla, no liberar el activo al flujo de caja/garantía hasta corregir o documentar excepción.

## Estándares iniciales

### INOVA Quantum

- Primario: Code 128.
- Texto visible: identificador operativo, ejemplo `Q00525499`.
- El `-xx` no se agrega por inferencia.
- Plantilla inicial: `inova_quantum_code128_v1`.
- Medida inicial de diseño: 52 × 18 mm; pendiente de validación física.

### Sercel DFU

- Primario actual: Code 128 por compatibilidad con LS2208.
- Texto visible: serial/ID confirmado.
- No se clona el Data Matrix original hasta leer y documentar su contenido real.
- Plantilla inicial: `sercel_dfu_code128_v1`.

### Teléfonos

- Primario: QR + número económico visible.
- Payload: identidad estable (`asset_id`/económico), no responsable, grupo, proyecto ni ubicación mutable.
- No grabar directamente una carcasa/tapa sin validar material y posición segura.
- Plantilla inicial: `phone_qr_economic_v1`.

## Criterios para aprobar una plantilla

Una plantilla pasa de `calibration_required=true` a aprobada solamente cuando:

1. la medida real coincide con el diseño;
2. el jig coloca repetidamente la marca dentro de tolerancia;
3. se leen al menos 20 pruebas consecutivas con el lector real, desde orientaciones/distancias de uso razonables;
4. se repite la prueba tras limpieza/manipulación para detectar bajo contraste;
5. no existe daño de carcasa ni riesgo por material;
6. se documenta el perfil de máquina/material.

Para producción crítica puede añadirse un verificador ISO/IEC de código; la simulación digital del proyecto no sustituye verificación física certificada.

## Adopción de ajustes ya validados en taller (v0.3)

Si el taller ya posee una combinación de velocidad/potencia/pasadas que produce grabados visibles y estables, ésta debe ser el **punto de partida**. Exportar el `.clb/.lbrn2/.lbset` o bundle y asociarlo al trabajo. No modificar potencia/velocidad sólo por introducir Code 128: primero se prueba geometría/tamaño con el mismo preset.

El criterio de aceptación cambia de “se ve” a “se ve + se lee de forma repetible”. Registrar máquina, plantilla, material/pieza, preset, fecha y lector utilizado.

Para captura manual, una plantilla puede exigir prefijo/sufijo. Para CSV el estándar es conservar el valor recibido a menos que la plantilla declare explícitamente `ensure_prefix_suffix`. Antes de producción siempre se muestra el resultado resuelto.


## Calibración y referencia del jig

Antes de aprobar una base nueva, generar el patrón `CALIBRATION ONLY` y medir `P0`, `PX` y `PY`. El evaluador detecta desplazamiento, escala, rotación y pérdida de escuadra; es diagnóstico y **no corrige automáticamente la máquina**. Para la estación inicial, usar jig fijo + Current Position/User Origin + Frame salvo que homing/origen absoluto estén físicamente validados.

Consultar `CALIBRATION_AND_ALIGNMENT.md`.

# Plan de aceptación física antes de producción

**Este documento es obligatorio antes de grabar nodos o teléfonos productivos.** Las pruebas automatizadas verifican geometría y decodificación de imágenes; no pueden demostrar el resultado fotoquímico/térmico de un láser sobre una carcasa real.

## 1. Preparación segura

- Trabajar con extracción adecuada de humos y protección correspondiente a la máquina.
- Nunca dejar el láser funcionando sin supervisión.
- Usar primero material de descarte, carcasa fuera de servicio o placa equivalente.
- No grabar plástico de composición desconocida hasta identificar que es apto para láser.
- En teléfonos, preferir placa/etiqueta metálica validada o una zona aprobada por modelo; no asumir que una trasera es segura por su apariencia.
- Confirmar foco, limpieza de lente y fijación mecánica.

## 2. Verificación de máquina

En la SCULPFUN real:

1. Conectar por USB.
2. Leer/registrar versión GRBL.
3. Registrar `$130` y `$131` (recorridos X/Y) y compararlos con el perfil de 400 × 410 mm.
4. Confirmar en LightBurn el dispositivo GRBL correcto y `S-Value Max` coherente con firmware.
5. Validar origen/coordenadas y comportamiento de `Frame`.
6. Fijar mecánicamente la base/jig; no confiar sólo en marcas visuales de la mesa.

Si estos pasos difieren, actualizar `config/machines/sculpfun_s9_pro_10w.json` antes de calibrar jigs.

## 3. Calibración de material

No usar valores de Internet como receta final. Crear una matriz de prueba sobre descarte del mismo material/recubrimiento:

- empezar con potencia baja / velocidad alta;
- incrementar energía gradualmente;
- buscar contraste suficiente sin derretir, carbonizar, deformar o atravesar;
- registrar foco/distancia, velocidad, potencia, número de pasadas y condiciones.

El perfil de material aprobado debe vivir fuera del motor de diseño y asociarse a máquina + material + revisión.

## 4. Aceptación Code 128 — INOVA/Sercel

Para cada candidato de configuración:

1. Grabar al menos 20 IDs/pruebas consecutivas distintas.
2. Confirmar lectura con el **lector real de operación**. El equipo confirmado por fotografía es Steren COM-597; si existe una estación con LS2208 u otro lector 1D, repetir también allí.
3. Probar lectura en al menos:
   - frontal normal;
   - ligera inclinación;
   - distancias prácticas del proceso;
   - iluminación habitual.
4. Confirmar que la cadena escaneada es exactamente la esperada.
5. Probar inspección visual rápida del texto humano.
6. Repetir tras limpieza normal y abrasión controlada equivalente al manejo esperado.

Criterio de aprobación recomendado: 20/20 lecturas correctas consecutivas en la condición normal y ausencia de falsos IDs.

## 5. Aceptación QR — teléfonos/activos

1. Usar el módulo inicial de 0.50 mm y quiet zone de 4 módulos.
2. Probar al menos dos cámaras/teléfonos o un lector 2D aprobado.
3. No eliminar el texto humano aunque QR funcione.
4. Validar que el payload sólo contiene el ID estable deseado.

## 6. Calibración del jig

Los archivos `*_estimate.json` o `*_calibration.json` se consideran provisionales hasta medir la base real.

Proceso:

1. colocar piezas sin grabar;
2. usar preview/Frame con potencia mínima que no marque;
3. ajustar `origin_x_mm`, `origin_y_mm`, `pitch_x_mm`, `pitch_y_mm`, `mark_offset_x_mm`, `mark_offset_y_mm`;
4. comprobar primera y última posición del jig;
5. realizar un lote sacrificial completo;
6. marcar `calibration_required=false` sólo cuando se haya aprobado físicamente.

## 7. Ensayo de error humano

Ejecutar deliberadamente estos casos:

- CSV `Q00525499`, pieza física `Q00525498` → debe bloquear exportación.
- slot vacío → debe bloquear si se exige confirmación.
- fila correcta en slot incorrecto → debe bloquear por ID físico.
- escaneo posterior distinto → no debe marcar el activo como verificado.

## 8. Piloto recomendado

Fase 1: 10 nodos fuera de servicio / descartados.

Fase 2: 20–50 nodos recuperados reales bajo supervisión, conservando el método actual como contingencia.

Fase 3: comparar métricas:

- tiempo por nodo;
- errores detectados antes de grabar;
- porcentaje de lectura al primer intento;
- excepciones manuales en caja/garantía;
- retrabajos;
- daño superficial o ilegibilidad.

Sólo después aprobar la plantilla como estándar productivo.

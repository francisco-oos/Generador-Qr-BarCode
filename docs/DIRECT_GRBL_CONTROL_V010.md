# Control directo GRBL v0.10 — experimental

## Alcance

Esta rama agrega una capa de control directo para **GRBL 1.1** sobre la evolución Laser Design Studio v0.9. No sustituye los flujos externos: LightBurn, Sculpfun Space y LaserGRBL siguen siendo opciones válidas de producción.

La primera máquina habilitada es el perfil `sculpfun_s9_pro_10w`. Los perfiles genéricos permanecen con control directo deshabilitado.

## Principios

1. No se acepta G-code arbitrario enviado por el navegador.
2. El cliente entrega SVG; Marking Studio extrae geometría lineal saneada y crea un `job_id` opaco.
3. La potencia/velocidad/pasadas provienen de un preset local marcado como validado en la **misma máquina y superficie**.
4. No se escriben automáticamente ajustes GRBL (`$30`, `$32`, pasos/mm, límites, homing, etc.).
5. El origen experimental es **posición actual**. No se presume homing.
6. Antes de Start es obligatorio ejecutar Frame en el mismo puerto con `M5`.
7. Start vuelve a leer `$I` y `$$` en la misma conexión y exige `$32=1` y `$30>0`.
8. El estado COMPLETE sólo se emite cuando, además de terminar el streaming, GRBL responde `Idle`.
9. Pause = feed hold `!`; Resume = cycle start `~`; Abort = hold + soft reset `0x18`.
10. Jog usa `$J=G91` y nunca enciende el láser.

## Operaciones

### line_engrave

Recorre los paths SVG con el preset de grabado validado.

### fill_engrave

Convierte contornos cerrados a hatch horizontal usando exactamente `interval_mm` del preset validado.

### cut

Recorre contornos con las pasadas, velocidad, potencia y modo M3/M4 del preset de corte validado.

## Geometría admitida

El compilador directo acepta SVG aplanado con:

- `svg`;
- `g`;
- `path`;
- `metadata/title/desc` (metadata se ignora para toolpath);
- comandos de path lineales M/L/H/V/Z, absolutos o relativos.

Los paths compuestos se separan en subpaths independientes. Esto es indispensable para QR/Code128, donde muchos módulos viven dentro de un solo atributo `d`.

Se rechazan:

- C/Q/A/S/T (curvas/arcos sin discretización validada);
- transforms;
- scripts, use, foreignObject, imágenes u otros elementos no lineales;
- coordenadas fuera de la cama declarada;
- geometría demasiado compleja.

Para SVG de Marking Studio con texto, use producción + `text_as_paths=true`.

## Plantillas incluidas

En `samples/laser_process_templates/`:

- `line_engrave_card.svg`;
- `fill_engrave_patch.svg`;
- `cut_geometry_coupon.svg`;
- `cut_papercut_panel.svg`.

También pueden generarse desde la UI/API. Ninguna contiene potencia/velocidad.

## Flujo de operador

```text
Diseño / QR / foto / papel picado
        ↓
preflight geométrico
        ↓
seleccionar preset local validado
        ↓
Compilar job
        ↓
seleccionar puerto
        ↓
FRAME (M5 / láser apagado)
        ↓
verificación física
        ↓
confirmar material + protección
        ↓
START
        ↓
RUNNING / HOLD / DRAINING
        ↓
GRBL Idle
        ↓
COMPLETE
```

## Seguridad física

El software no puede comprobar por sí solo extracción de humos, material real, protección ocular, presencia de personas/animales, fijación de la pieza ni riesgo de incendio. Esas confirmaciones permanecen explícitas antes de Start.

No se convierte una tabla de parámetros de Internet en un preset ejecutable. Los valores de referencia se usan para investigación/material test; el control directo exige evidencia local validada.

## Controladores futuros

La arquitectura expone una frontera de driver, pero v0.10 sólo implementa GRBL 1.1. Ruida, Trocen, TopWisdom, galvo y controladores propietarios no se tratan como GRBL por analogía.

## Validación sin máquina

CI usa un transporte GRBL simulado para comprobar:

- consulta de controlador;
- Frame sin M3/M4;
- compilación de potencia porcentual contra `$30`;
- streaming de G-code generado internamente;
- retorno al origen lógico;
- espera de `Idle`;
- rutas FastAPI;
- bloqueo de Start sin confirmaciones;
- rechazo de presets no validados;
- compatibilidad con Code128 de producción.

La aceptación física sobre SCULPFUN sigue pendiente hasta probar material sacrificial.

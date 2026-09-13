# PRE v0.8.0 — línea base 0.7.1

**Base autoritativa:** `server-oficina-marking-studio-v0.7.1.zip`  
**Host:** Linux x86_64 · Python 3.13.5 · Node disponible  
**Fecha:** 2026-09-13

La línea base se ejecutó antes de aceptar 0.8.0. Debido al límite de ejecución del runner, pytest se dividió en tres grupos; los 158 tests del paquete se ejecutaron y pasaron.

| Verificación | Resultado |
|---|---|
| Tests recolectados | 158 |
| Pytest | **158/158 PASS** |
| Grupo 1 | 24.71 s |
| Grupo 2 | 11.24 s |
| Grupo 3 | 26.67 s |
| `compileall` | PASS en la base/revisión 0.7.1 |
| `node --check` | PASS en la base/revisión 0.7.1 |
| Frontera de máquina | `$I` / `$$`, sin streaming productivo |

## Benchmark PRE repetido en este host

- 1,200 registros, jig 12 → 100 cargas;
- 2,500 renders individuales: **2.167 s · 1,153.5 marcas/s**;
- 1,200 marcas vectoriales: **0.995 s**;
- PNG de cama completa a 300 dpi: **5.357 s**;
- estado: PASS.

## Función negativa disponible en 0.7.1

0.7.1 ya incluía un `engraving_mode=negative_background` por elemento de código. Era una primera implementación útil para probar relieve, pero no modelaba todavía:

- polaridad a nivel de trabajo/plantilla;
- alcance `codes/all`;
- campo `islands/template`;
- margen;
- compensación de kerf;
- biblioteca validada con evidencia de scanner;
- comparación y cupón de caracterización;
- sufijo/manifiesto de seguridad para todo el trabajo.

## Invariantes PRE que no deben romperse

- motores Code128/Code39/QR/Data Matrix sin sustitución;
- SVG semántico/IDs únicos de 0.7.0;
- Excel/CSV flexible;
- conciliación física bloqueante;
- preflight positivo;
- `SAFE_GRBL_COMMANDS = ($I, $$)`;
- `direct_laser_job_streaming=false`;
- plantillas/materiales/jigs/lectores como configuración, no ramas por fabricante.

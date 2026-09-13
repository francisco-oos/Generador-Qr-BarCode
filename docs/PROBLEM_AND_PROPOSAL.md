# Problemática, propósito y propuesta

Fecha de revisión: 2026-09-12

## Problema operativo observado

Los nodos que conservan su etiqueta de fábrica pueden identificarse visualmente y también mediante lector. Cuando la etiqueta se pierde o una unidad pasa por reparación/restauración, el taller recupera la identidad escribiendo o grabando un número visible. Ese procedimiento conserva la inspección humana, pero si el marcado queda sólo como texto obliga a volver a teclear o verificar manualmente durante recepción, caja, garantía, inventario o conciliación.

Las fotografías de operación muestran una evolución real del proceso: primero se anotaba una parte numérica con marcador y actualmente ya se graba un identificador operativo como `Q00525499`. La mejora propuesta no elimina ese texto: lo conserva y agrega una representación legible por máquina.

## Propósito

Estandarizar el marcado físico de activos sin sustituir los sistemas del fabricante ni el software de la grabadora. Para cada tipo de activo se define una plantilla versionada que controla:

- qué dato es la identidad operativa;
- qué dato se muestra como texto;
- qué simbología se usa (Code 128, QR, Data Matrix u otra soportada);
- dimensiones y quiet zones;
- reglas opcionales de prefijo/sufijo;
- posición en un jig/base;
- política de conciliación física;
- perfil de máquina y preset de material usado;
- evidencia de exportación y posterior verificación por escaneo.

## Solución propuesta

`Server Oficina Marking Studio` es la capa de negocio y generación. LightBurn/LaserGRBL continúan siendo la capa de máquina. Esto permite aprovechar la SCULPFUN existente y sus ajustes ya probados, evitando crear un segundo controlador de láser.

Flujo:

```text
BD / CSV / captura manual
        ↓
normalización + prefijo/sufijo según plantilla
        ↓
plantilla física versionada
        ↓
asignación a posición del jig
        ↓
conciliación: ID físico escrito/escaneado = fila CSV
        ↓
SVG/PNG + manifiesto + preset de material + histórico
        ↓
LightBurn / LaserGRBL
        ↓
SCULPFUN / otra máquina compatible con el formato
        ↓
escaneo posterior
        ↓
VERIFICADO
```

## Decisiones de identidad

### INOVA Quantum

Identificador operativo inicial: `Q00xxxxxx`, por ejemplo `Q00525499`. El Code 128 y el texto visible contienen ese mismo valor. El sufijo de fábrica `-xx` no se inventa ni se vuelve obligatorio mientras el proceso de operación no lo requiera. Si se conoce, se conserva como dato adicional.

### Sercel

La primera plantilla de producción usa Code 128 + número visible porque el lector 1D disponible puede procesarlo. La plantilla Data Matrix se conserva como experimental hasta validar un lector 2D y confirmar el contenido de los símbolos de fábrica.

### Teléfonos y otros activos

Se utiliza identidad interna estable (por ejemplo `TEL-0037`) con QR + texto. El QR no debe codificar responsable, grupo, proyecto o ubicación porque esos atributos cambian; resuelve una identidad estable que el sistema usa para consultar el estado actual.

## Reducción de error humano

El control importante no es solamente generar un código. Para un lote importado, cada posición del jig exige comparar la identidad escrita/escaneada físicamente con la fila que se pretende grabar. Una discrepancia bloquea la exportación. El manifiesto conserva posición, fila, activo, plantilla y trabajo.

## Evolución hacia Server Oficina

La versión standalone mantiene SQLite y una licencia local. La integración futura no debe compartir directamente ese archivo: Marking Studio enviará eventos de `mark_requested`, `mark_exported`, `mark_verified` y la referencia de plantilla/preset al Tracking Core de Server Oficina. El activo continuará conservando su identidad e historial entre proyectos y reasignaciones.

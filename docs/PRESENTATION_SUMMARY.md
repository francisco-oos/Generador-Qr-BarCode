# Propuesta de mejora: Estandarización de marcado y trazabilidad física

## Situación actual

Cuando una etiqueta se deteriora o pierde, el equipo puede quedar identificado sólo con un número escrito o grabado. Esto permite verlo manualmente, pero obliga a introducir/verificar información a mano en procesos donde normalmente se usa escáner.

## Mejora propuesta

Aprovechar la SCULPFUN S9 Pro existente para reconstruir una identificación **humana + escaneable** bajo un estándar controlado:

```text
Dato autorizado → plantilla → reconciliación física → grabado → escaneo → histórico
```

No se propone sustituir LightBurn ni modificar la máquina. Se agrega un generador de trabajos que reduce transcripción y hace repetible la posición/formato.

## Beneficios esperados

- recuperación de lectura automática en nodos sin etiqueta;
- reducción de errores al capturar IDs;
- identificación visual rápida cuando sólo hay pocos equipos;
- procesos por lote desde CSV;
- trazabilidad de qué se grabó, cuándo y con qué plantilla;
- reutilización de la misma plataforma para INOVA, Sercel, teléfonos, radios, laptops y futuros activos;
- preparación para conexión con Server Oficina.

## Control del error humano

El sistema no acepta simplemente el orden del CSV. Cada posición del jig pide confirmar el ID visible de la pieza. Si no coincide, bloquea la exportación. Después del grabado se vuelve a escanear.

Esto crea dos controles independientes:

```text
ANTES: pieza física == CSV
DESPUÉS: código grabado == ID esperado
```

## Infraestructura reutilizada

- SCULPFUN S9 Pro 10W existente;
- PC existente;
- LightBurn o LaserGRBL;
- lector 1D Zebra/Symbol LS2208 observado;
- bases/jigs actuales, una vez medidas/calibradas.

## Piloto sugerido

1. Validar 10 piezas de descarte.
2. Aprobar tamaño/contraste de Code 128 con el lector real.
3. Calibrar jig.
4. Ejecutar 20–50 nodos reales supervisados.
5. Medir tiempo, porcentaje de lectura, errores evitados y retrabajo.
6. Aprobar versión estándar.

## Indicadores

- `% lectura al primer intento`;
- `errores de mismatch detectados antes de grabar`;
- `tiempo medio por activo`;
- `excepciones manuales en garantía/caja`;
- `regrabados/retrabajos`;
- `activos con identificación reconstruida y verificada`.

## Alcance de esta candidata

El software y sus pruebas digitales están terminados como candidata a piloto. La aprobación productiva depende deliberadamente de la prueba física sobre las carcasas reales, porque potencia, velocidad, foco y contraste no pueden verificarse de forma responsable sin la máquina/material delante.

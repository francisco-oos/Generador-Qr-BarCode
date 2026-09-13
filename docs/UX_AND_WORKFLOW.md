# UX y flujo operativo — Marking Studio v0.6.2

## Objetivo de la interfaz

La interfaz debe servir a dos perfiles sin duplicar la aplicación:

- **Operador guiado:** necesita generar, acomodar, exportar y verificar sin conocer JSON, GRBL ni detalles internos.
- **Técnico/administrador:** necesita crear plantillas, calibrar jigs, importar presets ya validados, revisar configuración y diagnosticar la estación.

La decisión principal de UX es **organizar por tarea y no por tecnología**. El operador piensa “marcar un teléfono” o “procesar una caja de nodos”, no “abrir el motor SVG”.

## Arquitectura de información

La navegación se agrupa en tres zonas:

### Operación

1. **Inicio** — punto de entrada y atajos por objetivo.
2. **Generador** — un activo / una identidad.
3. **Lotes / CSV** — muchos activos, mapeo y jig.
4. **Verificar** — comprobación posterior al grabado.

### Diseño

5. **Estudio visual** — composición reusable de plantillas.

### Control

6. **Histórico** — auditoría.
7. **Materiales** — presets del taller y referencias.
8. **Calibración** — base/jig y puntos de referencia.
9. **Sistema** — licencia, importadores y diagnóstico; oculto en modo guiado.

Esta separación reduce carga cognitiva: primero se ejecuta el trabajo, después se diseña o administra.

## Pantalla Inicio

La portada responde una sola pregunta: **“¿Qué desea hacer?”**. Expone cuatro acciones de alto uso:

- marcar un equipo;
- procesar una lista/CSV;
- crear o ajustar una plantilla;
- verificar un grabado.

También muestra un resumen de catálogo (número de plantillas, máquinas y lectores) para detectar rápidamente una carga incompleta de configuración.

## Generador individual

### Flujo

1. Elegir plantilla.
2. Capturar sólo los campos definidos por esa plantilla.
3. Ver la previsualización real actualizarse mientras se escribe.
4. Descargar SVG (preferido) o PNG.
5. Abrir el artefacto en el software de la máquina.
6. Aplicar el preset validado, hacer Frame y grabar.
7. Verificar por escaneo.

### Razón de diseño

La vista previa se mantiene al lado de los datos para que el usuario relacione inmediatamente **dato → objeto grabable**. No se muestran controles de potencia/movimiento porque pertenecen al software de la máquina.

## Lotes / CSV

El flujo se expresa con un stepper visible:

1. **Datos** — CSV, TXT o serie controlada.
2. **Mapeo** — qué columna alimenta cada campo de plantilla.
3. **Posiciones** — jig y conciliación física.
4. **Salida** — ZIP de trabajo o SVG individuales.

El CSV **no necesita un esquema rígido**. Puede contener:

- una sola columna sin encabezado;
- una sola columna con encabezado;
- varias columnas con nombres libres.

El sistema propone un mapeo, pero el usuario puede corregirlo. La vista previa del primer registro se recalcula tras cambiar el mapeo para detectar errores antes de acomodar equipo real.

## Estudio visual

El patrón de interacción sigue un editor visual convencional:

- **izquierda:** herramientas y campos de datos;
- **centro:** lienzo y SVG real;
- **derecha:** propiedades y lista de capas/elementos.

La lista de capas es importante porque un QR pequeño, una línea o elementos superpuestos pueden ser difíciles de seleccionar con el mouse. Cada objeto conserva coordenadas y medidas en milímetros; el canvas es sólo una representación interactiva.

La vista “SVG real” usa el mismo backend de producción. De esta forma no hay dos motores distintos, uno para diseño y otro para exportación.

## Modo guiado vs experto

### Guiado

Oculta detalles que no son necesarios para producción diaria, especialmente el área **Sistema** y los editores JSON. Mantiene instrucciones breves orientadas al siguiente paso.

### Experto

Expone:

- JSON de plantillas/jigs;
- importadores LightBurn/LaserGRBL;
- diagnóstico GRBL read-only;
- evaluación geométrica detallada;
- configuración avanzada.

El modo cambia visibilidad, no reglas de seguridad: incluso en experto Marking Studio no transmite movimiento, potencia ni disparo.

## Principios de visibilidad

1. **Preview cerca de la edición.**
2. **Acción primaria única por etapa.** Los botones azules representan el siguiente paso más probable.
3. **Advertencias en contexto.** No se esconden problemas de calibración/material en un log separado.
4. **Datos técnicos progresivos.** Un operador no ve JSON/GRBL si no los necesita.
5. **Unidades siempre explícitas.** Las dimensiones visibles se expresan en mm y los ajustes de velocidad/potencia indican unidad.
6. **Estado de lote visible.** Registro actual, capacidad de jig y número de carga permanecen a la vista.
7. **Salida diferenciada.** Preview/guías nunca se presentan como el archivo productivo.

## Revisión de accesibilidad y operación

- navegación y botones mantienen texto, no dependen sólo de iconos;
- el diseño responde a pantallas estrechas sin ocultar funciones esenciales;
- los lectores USB tipo teclado funcionan con inputs estándar;
- el operador puede seleccionar elementos del diseñador tanto por canvas como por lista de capas;
- las acciones destructivas permanecen diferenciadas;
- el modo guiado se conserva en `localStorage`, pero no modifica datos ni permisos.

## Criterio para futuras pantallas

Antes de agregar una nueva pestaña, preguntar:

1. ¿Es una tarea que el operador entiende como objetivo independiente?
2. ¿Puede integrarse como paso de una pantalla existente?
3. ¿Necesita estar visible en modo guiado?
4. ¿Su salida modifica diseño/datos o intenta controlar hardware?

Si intenta controlar hardware productivo, debe permanecer fuera de Marking Studio y resolverse mediante handoff al software de la máquina.

# Captura de los ajustes que el taller ya utiliza

Fecha de revisión: 2026-09-12

## Objetivo

No recalibrar desde cero una configuración que actualmente ya produce grabados visibles. La estrategia es **capturar, versionar y asociar** los parámetros que el área usa hoy al tipo de máquina, material/equipo y superficie. Después se optimiza geometría y legibilidad del QR/Code 128 sin perder la evidencia del ajuste original.

## Prioridad de configuración

1. Ajuste local ya validado: máxima prioridad.
2. Ajuste específico del fabricante para la misma máquina/material.
3. Referencia investigada.
4. Material Test conservador.

## Ruta A — Marking Studio corre en la misma PC que LightBurn

En **Sistema → Detectar LightBurn instalado**, la aplicación hace una exploración local limitada y de sólo lectura de rutas convencionales. Puede detectar:

- `prefs.ini` / `.lbprefs` — preferencias/rutas de LightBurn;
- `material_test_presets.lbmt` — Material Tests guardados;
- `.clb` — Material Library;
- `.lbset` — respaldo de Machine Settings;
- `.lbrn/.lbrn2` — proyectos con Cut Settings;
- `.lbzip` — User Bundle.

El archivo seleccionado se copia a `data/machine_imports/`, se calcula SHA-256, se parsean los valores compatibles y se registra el origen. **No se modifica el archivo original ni LightBurn.**

La detección local está deliberadamente restringida: la API sólo permite importar una ruta que haya sido devuelta previamente por el detector de LightBurn; no es un explorador arbitrario del sistema de archivos.

## Ruta B — Marking Studio está en Server Oficina y LightBurn en otra PC

Un servidor web no puede leer por sí solo el disco local de la PC del operador. En ese caso:

1. Exportar/copiar desde la estación de LightBurn el `.clb`, `.lbmt`, `.lbset`, `.lbprefs`, `.lbrn2` o `.lbzip`.
2. En Marking Studio, **Sistema → Importar configuración**.
3. Asociar el archivo al perfil `SCULPFUN S9 Pro 10W`.
4. Marking Studio archiva copia + hash y extrae los presets.

Esto mantiene la arquitectura válida cuando el backend migre a Debian/Server Oficina.

## Ruta C — Controlador GRBL

Con LightBurn/LaserGRBL desconectado del puerto, usar **Detectar puertos → Leer `$I + $$`**. La aplicación envía únicamente:

- `$I` — build/controller info;
- `$$` — settings actuales.

No envía `G0/G1`, `M3/M4/M5`, `$H`, `$n=...` ni potencia `S...`.

Esta lectura recupera límites/configuración del controlador, **no** la velocidad/potencia de una capa LightBurn. Esos valores viven en Cut Settings/Material Library/proyecto.

## LightBurn Material Test y `.lbmt`

LightBurn permite guardar/exportar presets de Material Test como `.lbmt`. Marking Studio v0.6 extrae:

- parámetro X/Y probado;
- mínimo/máximo y número de muestras;
- `MaterialCut`;
- `TextCut`;
- `BorderCut`.

Esto sirve para conservar los experimentos que el área ya realizó y evita transcribirlos manualmente.

Referencia oficial: https://docs.lightburnsoftware.com/latest/Reference/MaterialTest/

## Material Library `.clb`

La Material Library almacena ajustes reutilizables. Marking Studio extrae, cuando estén presentes:

- material;
- espesor/título;
- descripción;
- tipo de operación;
- velocidad;
- minPower / maxPower;
- interval;
- pasadas y otros Cut Settings legibles.

Referencia oficial: https://docs.lightburnsoftware.com/latest/Reference/MaterialLibrary/

## Qué información vive dónde

- `$30`, `$32`, `$130`, `$131`, pasos/mm, aceleraciones y límites: **controlador / Machine Settings**.
- velocidad, potencia, intervalo, pasadas y modo de capa: **Cut Settings / Material Library / proyecto / Material Test LightBurn**.
- barcode/QR, texto, prefijo, fuente de datos, tamaño y quiet zones: **plantilla Marking Studio**.
- pitch/offset físico: **jig Marking Studio**.
- serial/económico, proyecto, responsable, historial y estado: **Tracking Core / SQLite standalone**.

## Aprobación del estándar

Como el área ya tiene un ajuste que genera texto visible, el piloto debe partir de ese ajuste y medir primero la lectura de código. Una combinación se vuelve estándar sólo cuando quedan identificados:

`plantilla + revisión + jig + máquina + material/superficie + preset + lector + evidencia de escaneo`.

Si cambia cualquiera de esos componentes, se crea una nueva revisión; no se sobrescribe la historia anterior.


## LaserGRBL `.psh`

En Windows, LaserGRBL conserva una base de materiales de usuario en `%APPDATA%\LaserGRBL\UserMaterials.psh` y una base estándar puede aparecer como `StandardMaterials.psh`. Marking Studio 0.6 puede detectarlas/importarlas en modo sólo lectura, convertir campos reconocibles (modelo/material/operación/velocidad/potencia/ciclos) a presets portables y guardar hash/origen.

El importador acepta también `UserMaterial.psh` por compatibilidad con variantes históricas de nombre. No modifica ni sobrescribe la base de LaserGRBL.

## Captura manual de un ajuste ya probado

Si el área sólo conoce el ajuste porque lo tiene configurado en pantalla o lo anotó, **Materiales → Capturar ajuste del área** permite registrar máquina, material/superficie, modelo, operación, velocidad, potencia, pasadas, intervalo, referencia de foco, modo M3/M4, estado de validación y notas.

Para la S9 Pro revisada, el manual oficial usa la columna de enfoque de 50 mm. Un valor diferente sólo debe guardarse si representa una medición/offset deliberado de la instalación real y debe explicarse en notas.

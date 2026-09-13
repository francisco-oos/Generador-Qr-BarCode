# Matriz de compatibilidad y portabilidad

Fecha de revisión: 2026-09-12

## Aplicación Marking Studio

| Entorno | Estado de esta entrega | Instalador/launcher |
|---|---|---|
| Windows 10/11 x64, Python 3.12/3.13 | código/launchers + matriz CI definida; no ejecutado físicamente en este cierre | `install_windows.bat` / `run_windows.bat` |
| Linux x64, Python 3.13 | **ejecutado en el host de validación** | `install_linux.sh` / `run_linux.sh` |
| Linux ARM64, Python 3.12+ | arquitectura portable; no ejecutado en este cierre | `install_linux.sh` / `run_linux.sh` |
| macOS 12+, Python 3.12/3.13 | código/launchers + matriz CI definida; no ejecutado físicamente en este cierre | `install_macos.sh` / `run_macos.sh` |

El workflow `.github/workflows/ci.yml` define Windows/Linux/macOS × Python 3.12/3.13. El ZIP no afirma que esos runners se ejecutaron si no existe evidencia del servicio CI; la corrida local sólo certifica el host real.

## Software de máquina

| Software | Windows | macOS | Linux | Integración |
|---|---:|---:|---:|---|
| Sculpfun Space actual | Sí (Windows 10+) | Sí (macOS 13+) | No publicado | SVG/PNG + control SCULPFUN |
| LightBurn 2.1 actual | Sí | Sí | No | SVG + lectura/import de ajustes |
| LightBurn 1.7.08 legado | Sí | Sí | Sí | ruta Linux legado |
| LaserGRBL | Sí | No nativo | No nativo | SVG/PNG según flujo + import `.psh` |

Referencias:

- Sculpfun Space: https://www.sculpfun.com/pages/software
- LightBurn: https://docs.lightburnsoftware.com/2.1/GetStarted/InstallLightBurn/
- LaserGRBL: https://github.com/arkypita/LaserGRBL

## Artefactos LightBurn soportados

| Formato | Función |
|---|---|
| `.clb` | Material Library / Cut Settings |
| `.lbmt` | Material Test presets |
| `.lbset` | respaldo de Machine Settings |
| `.lbprefs`, `prefs.ini` | preferencias/rutas legibles |
| `.lbrn`, `.lbrn2` | Cut Settings de proyecto |
| `.lbzip` / `.zip` | User Bundle |
| `.psh` | base XML de materiales LaserGRBL |
| texto `.txt/.log` con `$$` | dump GRBL |

## Hardware

- SCULPFUN S9 Pro / GRBL: archivo + probe `$I/$$` read-only.
- Otros GRBL: diagnóstico compatible sólo tras crear/validar perfil independiente.
- DSP/Ruida/galvo/propietarios: handoff por archivo; probe GRBL no aplica.
- Zebra/Symbol LS2208: Code 128 y otras simbologías 1D; no QR/Data Matrix.
- Lector 2D: QR/Data Matrix según perfil/validación.

## Lectura del LS2208

Zebra publica para LS2208:

- patrón single-line;
- 100 scans/s;
- contraste mínimo 20 % de diferencia reflectiva;
- soporte de Code 128, Code 39, Code 93, UPC/EAN y otras simbologías 1D.

Fuente: https://www.zebra.com/us/en/products/spec-sheets/scanners/general-purpose-scanners/ls2208.html

Esto respalda el estándar inicial `Code 128 + texto visible` para los nodos que deban seguir usando el lector existente.

## Descubrimiento de ajustes y topología

| Topología | Detectar LightBurn automáticamente | Importar archivo manual | GRBL read-only |
|---|---:|---:|---:|
| Marking Studio y LightBurn en la misma PC | Sí | Sí | Sí, con puerto libre |
| Marking Studio en Server Oficina / LightBurn en otra PC | No puede leer el disco remoto por sí solo | **Sí** | sólo si el servidor tiene físicamente/accesiblemente el puerto |

La arquitectura preferida para producción futura es mantener la estación de grabado como nodo/cliente autorizado y sincronizar histórico con Server Oficina, no compartir un puerto USB arbitrariamente a través de la red.


## Sculpfun Space

SCULPFUN publica Sculpfun Space para Windows 10+ y macOS 13+, compatible con máquinas SCULPFUN no-galvo. Admite SVG, PNG, códigos de barras/QR, array layout, batch processing y presets/pruebas de material. Marking Studio usa ese software como otra ruta de handoff sin duplicar el control de la máquina.

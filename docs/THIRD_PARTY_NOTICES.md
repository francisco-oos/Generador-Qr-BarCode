# Third-party components

Este proyecto no redistribuye LightBurn ni LaserGRBL. LightBurn se instala/licencia por separado y LaserGRBL se obtiene de su proyecto oficial.

Dependencias Python principales declaradas por el proyecto y licencia reportada por su metadata instalada durante esta validación:

| Componente | Versión validada | Licencia / expresión |
|---|---:|---|
| FastAPI | 0.128.2 | MIT |
| Uvicorn | 0.48.0 | BSD-3-Clause |
| Pydantic | 2.13.4 | MIT |
| ReportLab | 4.4.9 | BSD |
| python-qrcode | 8.2 | BSD |
| Pillow | 12.3.0 | MIT-CMU |
| svglib | 1.6.0 | LGPL-3.0-or-later |
| cryptography | 46.0.4 | Apache-2.0 OR BSD-3-Clause |
| python-multipart | 0.0.29 | Apache-2.0 |

Dependencias sólo de QA incluyen pyzbar (MIT), OpenCV Python Headless (Apache-2.0), HTTPX (BSD-3-Clause) y pytest (MIT en la versión validada).

La tabla es un inventario técnico, no sustituye conservar los avisos/licencias exigidos por cada dependencia si el producto se distribuye comercialmente. Antes de una distribución externa o empaquetado binario conviene generar un bundle completo de notices/licencias desde el entorno de build.

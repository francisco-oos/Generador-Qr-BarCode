# Arquitectura de licenciamiento

## Marking Studio

La versión standalone usa `license/license.local.json`, firmado con Ed25519. `license/public_key.pem` permite verificar la firma; la clave privada no forma parte de la entrega.

Ventajas:

- funciona sin red en el taller;
- una modificación manual del payload invalida la firma;
- la UI y las APIs usan una interfaz común de proveedor de licencia;
- la implementación puede reemplazarse más adelante por Server Oficina.

La licencia incluida está identificada como **Internal Standalone** y está destinada a evaluación/uso interno del proyecto.

## LightBurn

LightBurn tiene su propio esquema y no forma parte de esta licencia. Según su documentación oficial, no es suscripción: la licencia permite seguir usando el software, incluye un periodo de actualizaciones y una licencia estándar dispone de tres seats simultáneos. La compra/activación se gestiona con LightBurn.

Marking Studio sólo exporta archivos compatibles; no interactúa con el mecanismo de activación de LightBurn.

## LaserGRBL

LaserGRBL es software libre y se distribuye por separado. Marking Studio no redistribuye ni modifica su ejecutable.

## Límite de máquinas en modo standalone

El payload actual contiene `machine_limit` para conservar desde hoy el contrato de licencia futuro. En una instalación totalmente desconectada, ese número no puede representar de forma antifraude un contador global de seats entre varias PCs: las instalaciones no tienen una autoridad compartida. La firma sí impide alterar el entitlement local sin invalidarlo. El conteo global debe aplicarse cuando `ServerOficinaLicenseProvider` o un servicio floating sea la autoridad.

Referencia LightBurn: https://docs.lightburnsoftware.com/latest/Licensing/

# Integración futura con Server Oficina

Marking Studio se diseñó como módulo desacoplado para que pueda usarse hoy de forma local y después conectarse al tracking central.

## Datos que deben persistirse

Ejemplo de estado de activo:

```text
asset_id: NODE-00525499
manufacturer: INOVA
manufacturer_operational_id: Q00525499
manufacturer_full_id: Q00525499-30   # sólo si se conoce
marking_status: VERIFIED
marking_template: inova_quantum_code128_v1
marking_job_id: ...
marking_machine: sculpfun_s9_pro_10w
marking_reason: LABEL_LOST
marked_at: ...
verified_at: ...
```

La identidad del activo no debe cambiar porque cambie de proyecto, responsable, grupo o unidad.

## Estados propuestos

```text
UNMARKED
TEMPORARY_MANUAL
PENDING_ENGRAVING
ENGRAVING_EXPORTED
ENGRAVED_PENDING_VERIFY
VERIFIED
REJECTED
```

## Razones de remarcado

- `LABEL_LOST`
- `LABEL_UNREADABLE`
- `CASE_REPLACED`
- `REPAIR_RESTORE`
- `STANDARDIZATION`
- `OTHER`

## Licencia central

El proveedor local actual devuelve una estructura común `status()`. En la integración futura, `ServerOficinaLicenseProvider` debe:

1. usar identidad de instalación/dispositivo;
2. autenticarse contra Server Oficina por LAN/VPN;
3. consultar entitlement/edición/funciones;
4. cachear una concesión firmada para tolerar caídas de red;
5. no almacenar una clave privada de firma en el cliente;
6. mantener una ventana offline configurable para el taller.

## Sincronización de histórico

El SQLite local puede conservarse como cola offline. Cuando Server Oficina esté disponible:

```text
local engraving_job
      │
      ├─ POST /marking/jobs
      │
      └─ POST /marking/verification
             │
             ▼
      tracking central / auditoría
```

La sincronización debe ser idempotente usando `job_id` UUID. Nunca debe duplicar movimientos por reintentos.

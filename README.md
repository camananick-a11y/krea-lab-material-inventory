# Krea Lab — Sistema de Inventario de Material

Sistema de inventario para filamento y resina de Krea Lab con descuento automático de stock, alertas de umbral, reportes de consumo y (fase futura) modelo predictivo.

**Stack:** Django 6 + Django REST Framework + PostgreSQL (Supabase) + JWT.

## Estado del proyecto

- Fase actual: **Semana 1 — Tarea diagnóstica** (9–11 sep 2026)
- Demo diagnóstica: una API de inventario básica con autenticación, alertas de stock y repo documentado.

## Setup local

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt

# 1. Copiar .env.example a .env y completar DATABASE_URL (Supabase)
copy .env.example .env

# 2. Aplicar migraciones
python manage.py migrate

# 3. Cargar datos de prueba (rubro impresión 3D)
python manage.py seed_demo_data

# 4. Levantar servidor
python manage.py runserver
```

**Usuario demo:** `demo` / `demo12345`

## Estructura del proyecto

```
krea_lab/        Proyecto Django (settings, urls)
accounts/        Usuarios y roles (admin, operator, purchasing) + JWT
inventory/       MaterialType, Material, AlertThreshold, StockMovement, PrintJob
reports/         Reporte de consumo y resumen de stock
```

## API

Base URL: `http://127.0.0.1:8000/api`

### Autenticación
| Método | Endpoint | Descripción |
|---|---|---|
| POST | `/api/auth/register/` | Crear usuario (público) |
| POST | `/api/auth/login/` | Obtener token JWT + perfil |
| POST | `/api/auth/token/refresh/` | Renovar token |
| GET/PATCH | `/api/auth/profile/` | Ver / editar perfil propio |

Usa el token como header: `Authorization: Bearer <access_token>`

### Documentación interactiva
| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/api/docs/` | UI Swagger para probar la API desde el navegador |
| GET | `/api/schema/` | Esquema OpenAPI (YAML) |

### Inventario
| Método | Endpoint | Descripción |
|---|---|---|
| GET/POST | `/api/inventory/materials/` | Listar / crear material |
| GET/PUT/PATCH/DELETE | `/api/inventory/materials/{id}/` | Ver / editar / borrar material |
| GET | `/api/inventory/materials/low_stock/` | Materiales bajo su umbral |
| GET/POST | `/api/inventory/material-types/` | Tipos (Filamento, Resina) |
| GET/POST | `/api/inventory/thresholds/` | Umbrales de alerta |
| GET/POST | `/api/inventory/movements/` | Movimientos de stock (IN/OUT) |
| GET/POST | `/api/inventory/print-jobs/` | Trabajos de impresión |

### Reportes
| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/api/reports/consumption/?material=1&from=2026-09-01&to=2026-09-30` | Consumo por material y período |
| GET | `/api/reports/summary/` | Resumen: total materiales y stock bajo umbral |

### Ejemplo de flujo

```bash
# 1. Login
curl -X POST http://127.0.0.1:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"demo","password":"demo12345"}'
# -> { "access": "...", "refresh": "...", "user": {...} }

# 2. Registrar salida de material (descuenta stock automáticamente)
curl -X POST http://127.0.0.1:8000/api/inventory/movements/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access>" \
  -d '{"material":1,"movement_type":"OUT","adjustment_type":"print_job","quantity":45,"reference":"Trabajo #1"}'

# 3. Listar alertas
curl http://127.0.0.1:8000/api/inventory/materials/low_stock/ \
  -H "Authorization: Bearer <access>"
```

## Modelo de datos

- **User** — usuario con rol (`admin`, `operator`, `purchasing`)
- **MaterialType** — tipo de material y unidad (`g`, `ml`)
- **Material** — nombre, marca, color, línea de negocio (ICON/PRINT/TECH/EDU), stock actual, costo
- **AlertThreshold** — umbral mínimo por material
- **StockMovement** — entrada/salida con motivo (compra, trabajo de impresión, ajuste, merma); descuenta/añade al stock en `save()`
  - valida que una salida no exceda el stock disponible
- **PrintJob** — trabajo de impresión (pieza, máquina, cantidad, datos del laminador); crea automáticamente el movimiento de salida

## Línea de negocio y vision futura

- **Fase 1 (sep–oct):** inventario real: bobinas/botellas individuales, entradas de compra, ajustes por pesaje, consumo por trabajo.
- **Fase 2 (oct–nov):** despliegue en AWS (EC2, PostgreSQL gestionada, HTTPS, monitoreo).
- **Fase 3 (nov):** modelo predictivo de agotamiento y sugerencia de compra.
- **Fase 4 (dic):** manual de operación y cierre.
- Integración futura: lectura del consumo estimado desde Bambu Studio (G-code/3MF) y Chitubox.
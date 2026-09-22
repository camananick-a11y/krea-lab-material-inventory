# Krea Lab — Sistema de Inventario de Material

Sistema de inventario para filamento y resina de Krea Lab con inventario **por bobinas/botellas individuales** (con QR, sede y restante calculado), descuento automático de stock, alertas de umbral, reportes de consumo y (fase futura) modelo predictivo.

**Stack:** Django 6 + Django REST Framework + PostgreSQL (Supabase) + JWT.

## Estado del proyecto

- Fase actual: **Semana 2 — Fase 1: inventario por unidades** (14–18 sep 2026)
- Implementado y validado: modelo de unidades (Sede, `MaterialUnit`, `PrintJobItem`, cambio de rollo multi-bobina), migración del histórico de Supabase y suite de pruebas en verde.
- Documentación: diseño → `docs/ARQUITECTURA.md` · API → `docs/MANUAL-API.md` · backlog → `docs/BACKLOG-CONGELADO-SEMANA-2.md`

## Plan de desarrollo

> Plan de desarrollo de producto — responsable: Nick Camana ·
> Sistema de inventario de filamento y resina con descuento automático · Septiembre – diciembre 2026

| Etapa | Alcance | Fechas | Estado |
|---|---|---|---|
| Semana 1 — Tarea diagnóstica | API base: auth JWT, materiales, movimientos IN/OUT, umbrales, reportes | 9–11 sep | Completado |
| Fase 1 — Inventario real | Unidades individuales con QR, sedes, entradas por compra, ajuste por pesaje, consumo por trabajo, reportes | 14 sep – 9 oct | En curso |
| Fase 2 — Despliegue en la nube | Contenedores, instancia, HTTPS + dominio, roles de acceso, monitoreo | 12 oct – 6 nov | Pendiente |
| Fase 3 — Modelo predictivo | Proyección de agotamiento por material y sugerencia de compra | 9–27 nov | Pendiente |
| Fase 4 — Cierre | Manual de operación, transferencia y llenado del PEA con evidencias | 30 nov – 4 dic | Pendiente |

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
inventory/       MaterialType, Material, Sede, MaterialUnit, AlertThreshold, StockMovement, PrintJob(+items)
reports/         Reporte de consumo y resumen de stock
scripts/         Verificación de post-migración contra producción (solo lectura)
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
| GET/POST | `/api/inventory/sedes/` | Sedes (CRUD) |
| GET/POST | `/api/inventory/units/` | Unidades bobina/botella (CRUD) |
| GET | `/api/inventory/units/low/` | Unidades por agotarse (fill_level = Por agotar) |
| GET | `/api/inventory/brands/` | Catálogo dinámico de marcas |
| GET/POST | `/api/inventory/thresholds/` | Umbrales de alerta |
| GET/POST | `/api/inventory/movements/` | Movimientos de stock (IN/OUT, por unidad o legacy) |
| GET/POST | `/api/inventory/print-jobs/` | Trabajos de impresión (items[] multi-bobina) |
| GET | `/api/inventory/u/{code}/` | Ficha pública por QR (anónimo: mínima; autenticado: completa) |

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

# 2. Registrar un trabajo con unidades (crea OUT por cada ítem; cambio de rollo = varios ítems)
curl -X POST http://127.0.0.1:8000/api/inventory/print-jobs/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access>" \
  -d '{"machine":"Bambu Lab X1C","print_name":"Gancho","items":[{"material_unit":3,"quantity_used":32}]}'

# 3. Listar alertas
curl http://127.0.0.1:8000/api/inventory/materials/low_stock/ \
  -H "Authorization: Bearer <access>"

# 4. Ficha de una bobina por su QR (sin token: tarjeta mínima pública)
curl http://127.0.0.1:8000/api/inventory/u/FIL-001/
```

## Etiquetas QR

```
# Genera hoja A4 imprimible con las etiquetas de todas las unidades
python manage.py generate_qr_labels --base-url https://inventario.krea.lab --output qr_labels.html
```

- Cada etiqueta muestra código, material, tipo, barra de nivel, sede y el QR de `{base_url}/api/inventory/u/{code}/`.
- Usa el **dominio final** (Fase 2) como `--base-url`; regenera la hoja cuando exista el dominio.
- Imprimir: abrir el HTML → Ctrl+P → A4. Por ejemplo: `python manage.py generate_qr_labels --base-url http://127.0.0.1:8000`.

## Modelo de datos

- **User** — usuario con rol (`admin`, `operator`, `purchasing`)
- **MaterialType** — tipo de material y unidad (`g`, `ml`)
- **Material** — nombre, marca, color, línea de negocio (ICON/PRINT/TECH/EDU), stock agregado (= suma del restante de sus unidades), costo
- **Sede** — sede física donde está la bobina/botella
- **MaterialUnit** — **bobina/botella física**: código único (etiqueta/QR), material, sede, acabado, color, hex, foto, peso bruto, tara, densidad (resina) y capacidad nominal
  - `remaining` = bruto − tara (filamento) o (bruto − tara) / densidad (resina)
  - `fill_level`: Lleno / Mitad / Cuarto / Por agotar · `status`: nueva / en_uso / agotada
  - `qr_url`: `/api/inventory/u/<code>/` (ver lectura de QR)
- **AlertThreshold** — umbral mínimo por material
- **StockMovement** — entrada/salida con motivo (compra, trabajo, ajuste, merma); con `material_unit` descuenta de la unidad; sin ella aplica a `current_stock` (legacy). Valida que una salida no exceda el stock disponible.
- **PrintJobItem** — unidad consumida en un trabajo (permite cambio de rollo a mitad de pieza)
- **PrintJob** — trabajo de impresión (pieza, máquina, datos del laminador, items); crea automáticamente un movimiento OUT por cada ítem

## Línea de negocio y visión futura

- **Fase 1 (sep–oct):** inventario real: bobinas/botellas individuales, entradas de compra, ajustes por pesaje, consumo por trabajo.
- **Fase 2 (oct–nov):** despliegue en la nube (instancia EC2, PostgreSQL gestionada, HTTPS, monitoreo).
- **Fase 3 (nov):** modelo predictivo de agotamiento y sugerencia de compra.
- **Fase 4 (dic):** manual de operación y cierre.
- Integración futura: lectura del consumo estimado desde los laminadores (G-code/3MF de Bambu Studio y Chitubox).
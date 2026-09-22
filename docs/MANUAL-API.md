# Manual de la API — Sistema de Inventario de Material de Krea Lab

**Base URL:** `http://127.0.0.1:8000/api` · **Autenticación:** todos los endpoints requieren
`Authorization: Bearer <access>` salvo los que se indican como **Pública**.

**Flujo de trabajo en Postman:** `POST /login/` → copiar `access` → usarlo como Bearer Token en cada
petición. El token `access` dura 12 horas; se renueva con `token/refresh`.
**Convención de métodos:** `POST` crea · `GET` consulta · `PUT` reemplaza · `PATCH` edita parcial ·
`DELETE` elimina · `{id}` = identificación del registro.

---

## 1. Autenticación — `/api/auth/`

- **POST `/register/`** *(Pública)* — crea un usuario. Requeridos: `username`, `password` (mín. 8) y `email`. Opcionales: `role` (admin/operator/purchasing), `phone`, `first_name`, `last_name`.
  Body → `{ "username": "nuevo", "password": "password123", "email": "nuevo@krea.lab" }`
  Resp 201 → `{ "id": 2, "username": "nuevo", "email": "...", "role": "operator", "phone": "", "first_name": "", "last_name": "" }`
- **POST `/login/`** *(Pública)* — entrega los tokens JWT y el perfil.
  Body → `{ "username": "demo", "password": "demo12345" }`
  Resp 200 → `{ "refresh": "eyJ...", "access": "eyJ...", "user": { "id": 1, "username": "demo", "role": "admin", ... } }`
- **POST `/token/refresh/`** *(Pública)* — renueva el token `access`.
  Body → `{ "refresh": "eyJ..." }` · Resp 200 → `{ "access": "eyJ-nuevo..." }`
- **GET `/profile/`** — perfil del usuario autenticado. Resp 200 → objeto `user` devuelto en el login.
- **PATCH `/profile/`** — edita parcialmente el perfil (`phone`, `first_name`, `last_name`, `username`, `email`).
  Body → `{ "phone": "+51 900 000 111" }` · Resp 200 → perfil actualizado.

---

## 2. Inventario — `/api/inventory/`

**Material (`material`):** `id, name, material_type(id), material_type_name, brand, color, business_line(ICON|PRINT|TECH|EDU|GENERAL), current_stock, unit_cost, is_below_threshold, threshold, units[], created_at, updated_at`
`units[]` = resumen por bobina/botella: `{ code, remaining, unit, fill_level, status, sede, qr_url }`. `current_stock` es la suma de esos `remaining`.

- **GET `/materials/`** — lista. Filtros opcionales: `?material_type=<id>&business_line=<...>&brand=<...>&search=<texto>`. Resp 200 → `[ material, ... ]`
- **POST `/materials/`** — crea un material. Requeridos `name`, `material_type` (id), `brand`; opcionales `color`, `business_line`, `current_stock`, `unit_cost` *(el `current_stock` se recalcula de las unidades al crear movimientos o editar unidades)*.
  Body → `{ "name": "PLA Basic", "material_type": 1, "brand": "Bambu Lab", "color": "Rojo", "business_line": "EDU", "current_stock": 500, "unit_cost": 89 }`
  Resp 201 → `{ "id": 7, ...material..., "threshold": null }`
- **GET/PUT/PATCH/DELETE `/materials/{id}/`** — consulta, reemplaza, edita o elimina. PUT requiere el cuerpo completo; PATCH solo el campo a cambiar (`{ "unit_cost": 92 }`); DELETE → 204. *(Un material con movimientos no se elimina: falla en la base de datos.)*
- **GET `/materials/low_stock/`** — solo materiales por debajo de su umbral. Resp 200 → `[ material, ... ]` (o `[]`).

**Tipo de material (`material-type`):** `id, name, unit(kg|g|ml|L)` — solo lectura.

- **GET `/material-types/`** → `[ { "id": 1, "name": "Filamento", "unit": "g" }, ... ]` · **GET `/material-types/{id}/`** → 1 objeto.

**Umbral (`threshold`):** `id, material(id), material_name, min_stock, notify_email, updated_at` — máximo 1 por material (si ya existe, se edita con PUT/PATCH).

- **GET `/thresholds/`** → `[ { "id": 1, "material": 1, "material_name": "...", "min_stock": "250.000", "notify_email": true, "updated_at": "..." } ]`
- **POST `/thresholds/`** — Body → `{ "material": 4, "min_stock": "200", "notify_email": true }` · Resp 201 → umbral creado.
- **GET/PUT/PATCH/DELETE `/thresholds/{id}/`** — consulta, edita o elimina (PATCH ej. `{ "min_stock": "400" }`; DELETE → 204).

**Movimiento (`movement`):** `id, material(id), material_name, material_unit(id), material_unit_code, movement_type(IN|OUT), adjustment_type(purchase|print_job|manual_in|manual_out|waste), quantity, reference, notes, created_by, created_by_name, created_at` — **IN suma stock, OUT resta** automáticamente. El listado ordena del más reciente al más antiguo.

- **GET `/movements/`** — Filtros: `?material=<id>&material_unit=<id>&movement_type=<IN|OUT>&adjustment_type=<...>&search=<texto>` → `[ movement, ... ]`
- **POST `/movements/`** — requeridos `movement_type`, `quantity`; opcionales `material_unit`, `material`, `adjustment_type` (default `manual_in`), `reference`, `notes`.
  - Con `material_unit` (recomendado): el material se deriva de la unidad; para resina la cantidad es **ml** y se convierte según la densidad.
  - Sin `material_unit` (legacy): se usa `material` y aplica sobre `current_stock`.
  Body OUT por unidad → `{ "material_unit": 3, "movement_type": "OUT", "adjustment_type": "manual_out", "quantity": 45, "reference": "Ajuste #001" }`
  Body IN legacy → `{ "material": 1, "movement_type": "IN", "adjustment_type": "purchase", "quantity": 500, "reference": "Compra #INV-007", "notes": "Proveedor" }`
  Resp 201 → `{ "id": 12, ...movement... }` · Error de stock insuficiente → 400 (indica el disponible de la unidad).
- **GET/PUT/PATCH/DELETE `/movements/{id}/`** — consulta, edita o elimina (DELETE → 204; borra el registro, **no** revierte el stock).

**Trabajo de impresión (`print-job`):** `id, machine, print_name, laminator_data(json), items[], created_by, created_at`
`items[]` = ítems de unidad consumida: `{ id, material_unit, material_unit_code, material_name, quantity_used }`

- **GET `/print-jobs/`** — `?search=<texto>` (print_name, machine) → `[ print-job, ... ]`
- **POST `/print-jobs/`** — crea el trabajo y sus movimientos **OUT por cada ítem** (cambio de rollo = varios ítems). `register_consumption` es idempotente.
  Body → `{ "machine": "Bambu Lab X1C", "print_name": "Gancho", "laminator_data": { "source": "bambu-studio" }, "items": [ { "material_unit": 3, "quantity_used": 32 } ] }`
  Resp 201 → `{ "id": 7, "...": "...", "items": [ { "id": 1, "material_unit": 3, "material_unit_code": "FIL-003", "material_name": "...", "quantity_used": "32.000" } ] }`
  *(Los campos `material`/`quantity_used` son legado y ya no se escriben.)*
- **GET/PUT/PATCH/DELETE `/print-jobs/{id}/`** — consulta, edita o elimina (PATCH ej. `{ "print_name": "Gancho v2" }`; DELETE → 204).

**Sede (`sede`):** `id, name, address, city, is_active`

- **GET `/sedes/`** → `[ { "id": 1, "name": "Villa El Salvador", "address": "", "city": "Lima", "is_active": true } ]`
- **POST `/sedes/`** — Body → `{ "name": "Lince", "city": "Lima" }` · Resp 201 → sede creada.
- **GET/PUT/PATCH/DELETE `/sedes/{id}/`** — consulta, edita o elimina una sede.

**Unidad (`unit`):** bobina/botella física. `id, code, material(id), material_name, brand, material_type, unit(g|ml), business_line, finish, color, hex_color, photo_ref, sede(id), sede_name, status(nueva|en_uso|agotada), fill_level(Lleno|Mitad|Cuarto|Por agotar), gross_weight, empty_weight, density, nominal_capacity, remaining_weight, remaining, percent, qr_url, created_at, updated_at`

- **GET `/units/`** — Filtros: `?material=<id>&sede=<id>&status=<nueva|en_uso|agotada>`; búsqueda: `?search=<code|material|marca|color|acabado>` → `[ unit, ... ]`
- **POST `/units/`** — Body → `{ "code": "FIL-007", "material": 1, "sede": 1, "finish": "Mate", "color": "Azul", "hex_color": "#0000FF", "gross_weight": "950", "empty_weight": "250", "density": "1.10", "nominal_capacity": "1000", "status": "nueva" }` · Resp 201 → unidad creada (recalcula el `current_stock` del material).
- **GET/PUT/PATCH/DELETE `/units/{id}/`** — consulta, edita o elimina. PATCH de utilidad para **pesaje**: `{ "gross_weight": "743" }` → recalcula `remaining`, `percent`, `fill_level` y la pasa a `agotada` si `gross ≤ empty`.
- **GET `/units/low/`** — solo unidades con `fill_level = Por agotar`.

**Marca (`brand`):** catálogo dinámico derivado de `Material.brand` (no es una tabla).

- **GET `/brands/`** → `[ { "name": "Bambu Lab", "materials_count": 3, "total_stock": "1353.000", "materials": [ { "id": 1, "name": "PLA Basic", "color": "Blanco", "unit": "g", "stock": "53.000", "business_line": "PRINT" }, ... ] } ]`
- **GET `/brands/{name}/`** — detalle de una marca por su nombre (p. ej. `Bambu+Lab`). 404 si no existe.

**Ficha pública por QR (`unit-public`):** — *Pública*.

- **GET `/u/{code}/`** — por `MaterialUnit.code` (404 si no existe).
  - **Anónimo:** tarjeta mínima sin stock ni costos → `{ code, material_name, brand, material_type, unit, business_line, finish, color, hex_color, photo_ref, status, fill_level, sede_name, qr_url }`
  - **Autenticado:** ficha completa del personal (`MaterialUnitSerializer`).
  - `qr_url` de cada unidad apunta a este endpoint; es lo que se imprime en la etiqueta.

---

## 3. Reportes — `/api/reports/`

- **GET `/consumption/`** — consumo (solo OUT) por período/material. Filtros: `?material=<id>&from=YYYY-MM-DD&to=YYYY-MM-DD`.
  Resp 200 → `{ "filters": { "material": null, "from": "...", "to": "..." }, "total_out_quantity": "345.000", "total_movements": 5, "rows": [ { "material_id": 1, "name": "PLA Basic", "brand": "Bambu Lab", "unit": "g", "quantity": 102.0 }, ... ] }`
- **GET `/summary/`** — resumen. Resp 200 → `{ "total_materials": 6, "low_stock_count": 0, "low_stock": [ { "material": "...", "id": 4, "current_stock": "357.000", "min_stock": "400.000" } ] }`

---

## 4. Documentación

- **GET `/schema/`** *(Pública)* — esquema OpenAPI. Para importar en Postman se usa `http://127.0.0.1:8000/api/schema/?format=json` (Import → Link).
- **GET `/docs/`** *(Pública)* — interfaz Swagger para probar la API desde el navegador.

---

## Notas

- Cualquier usuario autenticado (sin importar el `role`) puede usar todos los endpoints; el rol aún no restringe permisos.
- En producción (Supabase) los decimales se devuelven como `"345.000"`; en SQLite de pruebas como enteros.
- Los endpoints de solo lectura (`material-types`, `schema`, `docs`) no tienen operaciones de escritura.
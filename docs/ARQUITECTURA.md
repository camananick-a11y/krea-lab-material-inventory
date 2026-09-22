# ARQUITECTURA — Sistema de Inventario de Material de Krea Lab

> **Documento de diseño** · Rediseño a inventario por unidades individuales (Semana 2)
> **Responsable:** Nick Camana · **Estado:** implementado y validado contra la base de producción

## 1. Objetivo

Migrar el inventario de un modelo *agregado por material* (`current_stock` como contador) a un
modelo **por unidades físicas** (bobinas y botellas). Cada unidad cuenta con etiqueta/código QR,
sede, estado, peso bruto, tara y restante calculado. El stock agregado del material se conserva
como campo derivado (suma del restante de sus unidades) para no romper alertas, reportes ni la
aplicación de laminadores.

## 2. Modelo de datos

```
Sede
  - name (único), address, city, is_active
  Representa una sede física de Krea Lab (Villa El Salvador y Lince).

Material  (agregado; campo current_stock = suma del restante de sus unidades)
  - name, material_type (Filamento g / Resina ml), brand, color
  - business_line (ICON | PRINT | TECH | EDU | GENERAL)
  - current_stock (Decimal, derivado), unit_cost

MaterialUnit  (bobina/botella — la planilla Excel de Krea Lab como base de campos)
  - code (único)  → etiqueta física + QR: /api/inventory/u/<code>/
  - material (FK), sede (FK nullable)
  - finish, color, hex_color, photo_ref
  - gross_weight (g)   ← lectura de la balanza
  - empty_weight (g)   ← tara (envase vacío)
  - density (g/ml, default 1.10)  → solo resina
  - nominal_capacity (default 1000, en la unidad del material)
  - status: nueva | en_uso | agotada

AlertThreshold  (máximo 1 por material)  ↔ relación uno a uno con material

StockMovement
  - material (FK), material_unit (FK nullable; sin unidad = legacy)
  - movement_type: IN | OUT
  - adjustment_type: purchase | print_job | manual_in | manual_out | waste
  - quantity, reference, notes, created_by, created_at

PrintJob  (trabajo de impresión)
  - machine, print_name, laminator_data (JSON)
  - material / quantity_used  → CAMPOS LEGADO (nullable), por compatibilidad
  - items[] → PrintJobItem
        PrintJobItem: material_unit (FK) + quantity_used   ← multi-bobina (cambio de rollo)
```

Origen de los campos de `MaterialUnit`: la planilla de filamento/resina de Krea Lab
(ID único, peso bruto, tara, densidad, estado, acabado, hex, foto y datos de compra/factura/proveedor).

## 3. Reglas de cálculo

### 3.1 Restante de una unidad

- **Filamento (g):** `remaining = max(gross_weight - empty_weight, 0)`
- **Resina (ml):** `remaining = remaining_weight / density` (densidad típica 1.05–1.15)

### 3.2 Nivel de llenado (etiqueta y alertas de unidad)

`percent = remaining / nominal_capacity * 100` (limitado a 0–100):

| percent   | fill_level |
|-----------|------------|
| ≥ 75      | Lleno      |
| ≥ 50      | Mitad      |
| ≥ 25      | Cuarto     |
| < 25      | Por agotar |

### 3.3 Estado de la unidad

- En `save()`: si `gross_weight <= empty_weight` → `agotada`; si estaba `agotada` y recibe contenido (IN) → vuelve a `en_uso`.
- Siempre se recalcula el stock agregado del material: `Material.recalc_stock()` = suma del restante de sus unidades.

### 3.4 Movimientos

- **Con unidad** (`material_unit`): IN → `adjust_content(-qty)` (suma), OUT → `adjust_content(+qty)` (resta). En resina la cantidad es ml y se convierte a gramos con la densidad.
- **Sin unidad (legacy):** IN suma / OUT resta sobre `current_stock` directamente.
- **Validación:** un OUT con unidad no puede exceder `unit.remaining`; sin unidad, no puede exceder `material.current_stock`. El material se deriva automáticamente de la unidad.

### 3.5 Trabajos de impresión (cambio de rollo)

Un trabajo consume vía `items[]` una o más unidades (`PrintJobItem`). `PrintJob.register_consumption()`
crea un `StockMovement OUT print_job` por cada ítem (idempotente). El campo `quantity_used` se
distribuye entre los ítems; el total registrado por el trabajo = suma de `items.quantity_used`.

## 4. QR dinámico por rol

- `MaterialUnit.qr_url` → `GET /api/inventory/u/<code>/` (pública).
- **Anónimo** (proveedor/cliente): tarjeta mínima de identidad (código, material, marca, tipo, color, sede, nivel de llenado), **sin stock ni costos** (`UnitPublicSerializer`).
- **Autenticado** (personal): ficha completa del operador (`MaterialUnitSerializer`), con pesos, restante calculado, percent, estado y QR.
- El QR impreso en la etiqueta física codifica una URL estable del backend (`/api/inventory/u/<code>/`); no depende del estado de la unidad.

### 4.1 Etiqueta física — comando `generate_qr_labels`

Genera una hoja imprimible (A4) con todas las etiquetas:

```
.\venv\Scripts\python.exe manage.py generate_qr_labels `
  --base-url https://inventario.krea.lab --output qr_labels.html
```

- **Base URL**: dominio público final (despliegue de la Fase 2). Mientras no exista, se usa un placeholder y se regenera la hoja cuando haya dominio definitivo (los QR quedan viejos una vez impresos).
- Filtros opcionales: `--material <id>`, `--sede <id>`, `--status nueva|en_uso|agotada`.
- Formato: hoja A4, etiquetas de 92×35 mm (2 por fila), borde redondeado y `page-break-inside: avoid`.
- Campos por etiqueta: encabezado KREA LAB · INVENTARIO, código de la unidad (p. ej. `FIL-001`), material (`Marca Nombre Color`), tipo/unidad y acabado, barra de nivel con `fill_level`, sede, estado y QR (28×28) apuntando a `{base_url}/api/inventory/u/{code}/`.
- No expone stock ni costos en la etiqueta (misma política que la ficha anónima).

## 5. Migración del histórico (Supabase → unidades)

### 0002 — Esquema nuevo
Crea `Sede`, `MaterialUnit`, `StockMovement.material_unit` y `PrintJobItem`; `PrintJob.material` y
`PrintJob.quantity_used` pasan a nullable (legacy).

### 0003 — Datos históricos (RunPython idempotente)
- Guard: si ya existen `MaterialUnit` o no hay `Material`, no ejecuta nada (bases de datos vacías de prueba).
- Crea las sedes **Villa El Salvador** y **Lince**.
- Crea **una unidad por material** con `gross_weight = current_stock` (filamento) o `current_stock × 1.10` (resina, para que `remaining = current_stock` en ml).
- **Enlaza los 16 movimientos históricos** a su unidad (trazabilidad conservada).
- **PLA Rojo** (sin historial): crea la unidad con 500 y una entrada `IN manual_in` de 500 como registro de trazabilidad.
- **Restaura el umbral de PLA Blanco a 250** (se encontraba en 1200 por un artefacto de datos de demostración).
- Crea un `PrintJobItem` por cada `PrintJob` legado desde su `material`/`quantity_used`.

> Validado (2026-09-17) contra réplica del dump real: 7 unidades (FIL-001…005, RES-001…002),
> stock por material cuadra, 16 movimientos enlazados, entrada IN 500 de PLA Rojo, umbral 250 y
> 5 ítems de trabajo. Suite de pruebas completa 37/37 en verde.

## 6. Flujo de operación

1. **Compra / ingreso:** se crea la unidad (`code` nuevo) y un `StockMovement IN purchase` (con o sin `material_unit`). Para legado: IN sin unidad suma a `current_stock`.
2. **Pesaje de control:** se edita `gross_weight`/`empty_weight` de la unidad (recalcula restante y estado).
3. **Trabajo de impresión:** `POST /print-jobs/` con `items[]` = unidades consumidas. Cada ítem genera su OUT por unidad (cambio de rollo = varios ítems). `register_consumption` es idempotente.
4. **Ajuste manual / merma:** `POST /movements/` con `material_unit` y `adjustment_type` `manual_in`/`manual_out`/`waste`.
5. **Lectura de etiqueta:** el QR conduce a la ficha por rol (sección 4).

## 7. API (resumen)

| Endpoint | Descripción |
|---|---|
| `GET/POST/… /sedes/` | Sedes (CRUD) |
| `GET/POST/… /units/` | Unidades bobina/botella (CRUD) · `GET /units/low/` (fill_level = Por agotar) |
| `GET /brands/` · `GET /brands/{name}/` | Catálogo dinámico de marcas (derivado de `Material.brand`, sin tabla) |
| `GET/POST/… /movements/` | Movimientos con `material_unit` opcional |
| `GET/POST/… /print-jobs/` | Trabajos de impresión con `items[]` anidados |
| `GET /u/{code}/` | Ficha pública por QR (anónimo: mínima; autenticado: completa) |

Detalle completo de peticiones y respuestas: `docs/MANUAL-API.md`.

## 8. Pendientes y backlog

> Backlog congelado al cierre de la Semana 2: `docs/BACKLOG-CONGELADO-SEMANA-2.md`.

- Establecer el **dominio público final** y regenerar la hoja de etiquetas QR con él (la generación ya existe).
- Impresión física de las etiquetas y definición de impresora/cinta si aplica.
- Ficha web de unidad para el laminador (tarjeta `/u/{code}`).
- Alta de unidades desde orden de compra (auto-generar N unidades por ítem de compra).
- Lectura de consumo desde Bambu Studio / Chitubox (primera automatización de la Semana 4).
- Despliegue en la nube (Fase 2) con el dominio definitivo.
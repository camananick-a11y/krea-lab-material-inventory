# CIERRE DE SEMANA 2 — BACKLOG CONGELADO

> **Proyecto:** Sistema de inventario de filamento y resina (Krea Lab)
> **Responsable:** Nick Camana · **Fecha de cierre:** 18 de septiembre de 2026
> **Periodo:** Semana 2 — Levantamiento con producción y arquitectura (14–18 sep 2026)

## 1. Entregable de la Semana 2 (según el plan)

> "Cierre de fase: documento corto de arquitectura, modelo de datos validado con producción y backlog aprobado."

| Entregable | Cumplido | Evidencia |
|---|---|---|
| Sesión de levantamiento con producción | Cumplido | Decisiones de operación documentadas (ver Anexo A) |
| Rediseño del modelo: unidades individuales | Cumplido | `inventory/models.py` (Sede, MaterialUnit, PrintJobItem) |
| Definición del etiquetado físico (QR) | Cumplido | `docs/ARQUITECTURA.md` §4.1 · `generate_qr_labels` |
| Documento corto de arquitectura | Cumplido | `docs/ARQUITECTURA.md` |
| Modelo de datos validado con producción | Cumplido | Aplicado a Supabase (migraciones 0002/0003) y verificado con `scripts/check_supabase.py` · suite 37/37 |
| Backlog aprobado (congelado) | Cumplido | Este documento |

## 2. Backlog congelado al cierre de la Semana 2

A partir de esta fecha el alcance queda **congelado**. Las fases y entregables siguientes son los
aprobados y no se ampliarán durante la ejecución; las ideas nuevas se registran en la lista de
"Versión futura" (§4).

### Fase 1 — Inventario real de Krea Lab (semanas 3–5)

- **S3 (Núcleo):** registro de bobinas/botellas con etiqueta; entradas por compra (proveedor, precio, fecha); ajustes por pesaje en balanza; vista de stock por sede y por tipo con alertas; jornada de inventario físico (conteo + etiquetado).
- **S4 (Consumo):** registro de trabajos por ítem de unidad (gramos/ml reales); lectura del consumo estimado desde los archivos del laminador (G-code/3MF de Bambu Studio y archivo de Chitubox) como primera automatización; comparación semanal stock vs pesaje.
- **S5 (Reportes):** reportes por material/máquina/sede/línea (ICON, PRINT, TECH, EDU) con exportación a Excel; lista de reposición para compras; demo de fin de fase.
- **Entregable de fin de Fase 1:** inventario real operando en local (vie 9 oct).

### Fase 2 — Despliegue en la nube (semanas 6–9)

- **S6:** diagrama de arquitectura en la nube; Docker; usuario IAM con permisos mínimos + alarma de presupuesto.
- **S7:** VPC + instancia EC2 en capa gratuita; base de datos gestionada; migración de los datos de la Fase 1 sin perder histórico.
- **S8:** HTTPS + dominio/subdominio; acceso móvil en VES y Lince con roles (producción registra / compras consulta / administración configura).
- **S9:** monitoreo, respaldo automático y automatización del despliegue.
- **Entregable de fin de Fase 2:** sistema en producción usado a diario por el equipo (vie 6 nov).

### Fase 3 — Modelo predictivo de consumo (semanas 10–12)

- **S10:** preparación de datos (histórico sept–nov; consumo diario por tipo y sede; patrones).
- **S11:** proyección de agotamiento por material (regresión vs promedio móvil como línea base) y sugerencia de compra con tiempo de reposición.
- **S12:** integración en la pantalla de reposición inteligente; documento de precisión del modelo vs línea base.
- **Entregable de fin de Fase 3:** pantalla de reposición con proyección (vie 27 nov).

### Fase 4 — Cierre (semana 13, 30 nov – 4 dic)

- Manual de operación (producción y compras); documentación técnica y ruta de integración total con laminadores.
- Transferencia de repositorio, credenciales y guía de operación.
- Presentación final y llenado del PEA con evidencias.

## 3. Nota de alcance (riesgo "crecimiento del alcance")

Se cumple la condición del plan: *"El backlog se congela al cierre de la semana 2; las ideas nuevas
van a la lista de 'versión futura'."* Ningún requerimiento posterior a este documento modifica fases
o fechas; se gestiona como cambio formal solo si lo aprueba el responsable, con impacto evaluado en
alcance/tiempo/costo.

## 4. Lista de "Versión futura" (no entra en el alcance actual)

- Integración total del consumo con los laminadores sin intervención humana (descuento automático 100%).
- Aplicación móvil nativa (hoy la ficha QR es web responsiva).
- Notificaciones push / programadas de alertas de stock a compras.
- Panel de administración avanzado (migración a tabla de marcas real con de-duplicación).
- API pública (clave de cliente) para consultas de stock por terceros.
- Historial de precios de proveedores y comparador de cotizaciones.
- Control de lotes y fechas de vencimiento de resina.

---

## Anexo A — Decisiones del levantamiento (Semana 2)

1. La **planilla Excel** de filamentos/resinas es la base de campos de `MaterialUnit` (ID único, peso bruto, tara, densidad 1.10, estado, acabado, hex, foto; datos de compra/factura/proveedor en los movimientos).
2. **Sedes dinámicas**: entidad `Sede`; `Material.current_stock` se mantiene como suma del restante de sus unidades.
3. **Cambio de rollo** a mitad de trabajo soportado desde la Fase 1 vía `PrintJobItem` (multi-bobina).
4. **QR dinámico por rol**: URL estable `/api/inventory/u/<code>/`; anónimo → tarjeta mínima sin stock/costos; autenticado → ficha completa.
5. **Catálogo abierto**: marca/material/color libres; `Brand` = agregación dinámica (no tabla FK).
6. **Registro** = stock inicial + movimientos (IN/OUT automático por unidad o legacy).
7. **Correcciones de datos reales:** umbral de PLA Blanco a 250 (se encontraba en 1200) y entrada IN 500 para PLA Rojo, aplicadas por la migración 0003.
8. El modelo se aplicó a **Supabase (producción)** con las migraciones 0002/0003 el 17/09/2026 y quedó verificado (7 unidades, stock cuadrado, 16 movimientos enlazados, 5 ítems de trabajo).
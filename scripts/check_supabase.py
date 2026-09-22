"""Sanity check post-migración contra Supabase (SOLO LECTURA).

Usa la DATABASE_URL del entorno / .env (Supabase). No modifica nada.
Uso: .\\venv\\Scripts\\python.exe manage.py shell -c "exec(open(r'scripts/check_supabase.py').read())"
"""
import sys
from decimal import Decimal

from inventory.models import (
    AlertThreshold, Material, MaterialUnit, PrintJob, PrintJobItem,
    Sede, StockMovement,
)

errors = []

print('=== SANITY CHECK (post-migración) ===')

sedes = list(Sede.objects.all())
print(f'Sedes ({len(sedes)}):', ', '.join(s.name for s in sedes))
if len(sedes) != 2:
    errors.append(f'sedes != 2: {len(sedes)}')

units = list(MaterialUnit.objects.select_related('material', 'material__material_type', 'sede'))
print(f'Unidades ({len(units)}):')
for u in sorted(units, key=lambda x: x.code):
    print(f'  {u.code} | {u.material} | sede={u.sede.name if u.sede else None} '
          f'| gross={u.gross_weight} | remaining={u.remaining} | nivel={u.fill_level} | {u.status}')
if len(units) != 7:
    errors.append(f'units != 7: {len(units)}')

print('Cuadre stock agregado vs unidades:')
for mat in Material.objects.prefetch_related('units'):
    total = sum(u.remaining for u in mat.units.all())
    ok = mat.current_stock == total
    print(f'  {mat} | current_stock={mat.current_stock} | suma={total} | {"OK" if ok else "!! NO CUADRA"}')
    if not ok:
        errors.append(f'stock no cuadra para material {mat.id}')

moves = StockMovement.objects.select_related('material_unit')
total = moves.count()
with_unit = moves.exclude(material_unit__isnull=True).count()
print(f'Movimientos: {total} total | {with_unit} con unidad | {total - with_unit} sin unidad')
if total != 16 or with_unit != 16:
    errors.append(f'movimientos esperados 16/16 con unidad, visto {with_unit}/{total}')

m7_unit = MaterialUnit.objects.filter(code='FIL-005').first()
if m7_unit:
    m7_ins = StockMovement.objects.filter(
        material_unit=m7_unit, movement_type='IN', adjustment_type='manual_in')
    print(f'PLA Rojo (FIL-005): entradas manuales IN = {m7_ins.count()} '
          f'-> {", ".join(str(x.quantity) for x in m7_ins)}')
    if m7_ins.count() != 1 or m7_ins.first().quantity != Decimal('500.000'):
        errors.append('IN 500 PLA Rojo no verificado')

t1 = AlertThreshold.objects.filter(material__name='PLA Basic', material__brand='Bambu Lab',
                                   material__color='Blanco').first()
print(f'Umbral PLA Blanco: {t1.min_stock if t1 else "SIN UMBRAL"}')
if not t1 or t1.min_stock != Decimal('250.000'):
    errors.append('umbral PLA Blanco != 250')

items = list(PrintJobItem.objects.select_related('material_unit'))
print(f'PrintJobItems: {len(items)} | trabajos: {PrintJob.objects.count()}')
for it in items:
    print(f'  Trabajo #{it.print_job_id} {it.print_job.print_name!r} -> '
          f'{it.material_unit.code} -{it.quantity_used}')
if len(items) != 5:
    errors.append(f'print items != 5: {len(items)}')

print()
if errors:
    print('RESULTADO: ERRORES')
    for e in errors:
        print(f'  - {e}')
    sys.exit(1)
print('RESULTADO: OK — producción coherente con el modelo de unidades.')
sys.exit(0)
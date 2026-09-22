from decimal import Decimal

from django.db import migrations

# Datos reales de Supabase al cierre de la Semana 1 (dump 2026-09-17).
# La migración convierte el histórico (stock por contador de material) al
# modelo por unidades individuales (bobina/botella), preservando todo el
# histórico y decidiendo los puntos abiertos del diagnóstico.

THRESHOLD_RESTAURO = {1: Decimal('250')}


def migrate_legacy(apps, schema_editor):
    material = apps.get_model('inventory', 'Material')
    material_type = apps.get_model('inventory', 'MaterialType')
    unit = apps.get_model('inventory', 'MaterialUnit')
    sede = apps.get_model('inventory', 'Sede')
    movement = apps.get_model('inventory', 'StockMovement')
    threshold = apps.get_model('inventory', 'AlertThreshold')
    print_job = apps.get_model('inventory', 'PrintJob')
    print_item = apps.get_model('inventory', 'PrintJobItem')
    user = apps.get_model('accounts', 'User')

    if unit.objects.exists() or not material.objects.exists():
        return

    ves, _ = sede.objects.get_or_create(
        name='Villa El Salvador', defaults={'city': 'Lima'},
    )
    sede.objects.get_or_create(name='Lince', defaults={'city': 'Lima'})

    demo = user.objects.filter(username='demo').first()

    types = {t.name: t for t in material_type.objects.all()}

    fil_counter = 0
    res_counter = 0

    for mat in material.objects.order_by('id'):
        is_resin = mat.material_type.unit == 'ml'
        if is_resin:
            res_counter += 1
            code = f"RES-{res_counter:03d}"
        else:
            fil_counter += 1
            code = f"FIL-{fil_counter:03d}"

        current = unit.objects.create(
            code=code,
            material=mat,
            sede=ves,
            color=mat.color,
            finish='',
            gross_weight=Decimal('0'),
            empty_weight=Decimal('0'),
            density=Decimal('1.10'),
            nominal_capacity=Decimal('1000'),
            status='en_uso',
        )

        movement.objects.filter(material_id=mat.pk).update(material_unit=current)

        if not movement.objects.filter(
            material_id=mat.pk, movement_type='IN',
        ).exists():
            movement.objects.create(
                material=mat,
                material_unit=current,
                movement_type='IN',
                adjustment_type='manual_in',
                quantity=Decimal('500'),
                reference='Ajuste - stock inicial registrado el 2026-09-11',
                notes='PLA Rojo creado sin movimiento original; entrada de ajuste para trazabilidad.',
                created_by=demo,
            )

        if is_resin:
            gross = mat.current_stock * Decimal('1.10')
        else:
            gross = mat.current_stock
        unit.objects.filter(pk=current.pk).update(gross_weight=gross)

    for mat in material.objects.all():
        total = Decimal('0')
        for u in unit.objects.filter(material_id=mat.pk):
            if mat.material_type.unit == 'ml':
                remaining = u.gross_weight / u.density if u.density else u.gross_weight
            else:
                remaining = u.gross_weight
            total += remaining
        material.objects.filter(pk=mat.pk).update(current_stock=total)

    for mat_id, min_stock in THRESHOLD_RESTAURO.items():
        threshold.objects.filter(material_id=mat_id).update(min_stock=min_stock)

    for job in print_job.objects.all():
        target_unit = unit.objects.filter(material_id=job.material_id).first()
        if target_unit and job.quantity_used is not None:
            exists = print_item.objects.filter(
                print_job_id=job.pk, material_unit_id=target_unit.pk,
            ).exists()
            if not exists:
                print_item.objects.create(
                    print_job_id=job.pk,
                    material_unit_id=target_unit.pk,
                    quantity_used=job.quantity_used,
                )


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0002_sede_alter_printjob_material_and_more'),
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(migrate_legacy, migrations.RunPython.noop),
    ]
from datetime import datetime, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import User
from inventory.models import (
    AlertThreshold,
    Material,
    MaterialType,
    MaterialUnit,
    PrintJob,
    PrintJobItem,
    Sede,
    StockMovement,
)

MATERIALS = [
    {
        'name': 'PLA Basic', 'type': 'Filamento', 'unit': 'g',
        'brand': 'Bambu Lab', 'color': 'Blanco', 'line': 'PRINT',
        'stock': 1200, 'cost': 89.00, 'min_stock': 250, 'sede': 'Villa El Salvador',
    },
    {
        'name': 'PLA Basic', 'type': 'Filamento', 'unit': 'g',
        'brand': 'Bambu Lab', 'color': 'Negro', 'line': 'EDU',
        'stock': 800, 'cost': 89.00, 'min_stock': 300, 'sede': 'Lince',
    },
    {
        'name': 'PETG', 'type': 'Filamento', 'unit': 'g',
        'brand': 'eSun', 'color': 'Transparente', 'line': 'ICON',
        'stock': 650, 'cost': 99.00, 'min_stock': 200, 'sede': 'Villa El Salvador',
    },
    {
        'name': 'PLA Silk', 'type': 'Filamento', 'unit': 'g',
        'brand': 'Creality', 'color': 'Dorado', 'line': 'PRINT',
        'stock': 450, 'cost': 105.00, 'min_stock': 200, 'sede': 'Villa El Salvador',
    },
    {
        'name': 'Resina Estándar', 'type': 'Resina', 'unit': 'ml',
        'brand': 'Anycubic', 'color': 'Transparente', 'line': 'TECH',
        'stock': 800, 'cost': 65.00, 'min_stock': 250, 'sede': 'Villa El Salvador',
    },
    {
        'name': 'Resina Water-Washable', 'type': 'Resina', 'unit': 'ml',
        'brand': 'Elegoo', 'color': 'Gris', 'line': 'GENERAL',
        'stock': 350, 'cost': 72.00, 'min_stock': 300, 'sede': 'Lince',
    },
]

PRINT_JOBS = [
    ('Bambu Lab X1C', 'Portavasos ICON #12', 'Bambu Lab|PLA Basic|Blanco'),
    ('Bambu Lab X1C', 'Llaveros EDU - Lote 3', 'Bambu Lab|PLA Basic|Blanco'),
    ('Creality Ender 3', 'Prototipo TECH - Soporte', 'eSun|PETG|Transparente'),
    ('Elegoo Saturn 2', 'Miniatura de exhibición', 'Anycubic|Resina Estándar|Transparente'),
    ('Bambu Lab P1S', 'Figura escala PRINT - Serie 7', 'Creality|PLA Silk|Dorado'),
]

PRINT_CONSUMPTION = [45, 57, 69, 81, 93]

MULTI_COLOR_JOB = {
    'machine': 'Bambu Lab P1S',
    'print_name': 'Caja modular PRINT - 2 colores',
    'primary': 'Bambu Lab|PLA Basic|Blanco',
    'secondary': 'Creality|PLA Silk|Dorado',
    'qty_primary': 110,
    'qty_secondary': 40,
}


class Command(BaseCommand):
    help = 'Carga datos de prueba realistas del rubro de Krea Lab (bobinas/botellas individuales)'

    def handle(self, *args, **options):
        self.stdout.write('Creando usuario demo...')
        demo_user, created = User.objects.get_or_create(
            username='demo',
            defaults={
                'email': 'demo@krea.lab',
                'role': User.Role.ADMIN,
                'phone': '+51 999 000 111',
                'is_superuser': True,
                'is_staff': True,
            },
        )
        if created:
            demo_user.set_password('demo12345')
            demo_user.save()
            self.stdout.write('  + usuario demo creado')

        self.stdout.write('Creando sedes...')
        sedes = {}
        for name in ['Villa El Salvador', 'Lince']:
            sede, _ = Sede.objects.get_or_create(name=name, defaults={'city': 'Lima'})
            sedes[name] = sede

        self.stdout.write('Creando tipos de material...')
        filamento_type, _ = MaterialType.objects.get_or_create(name='Filamento', defaults={'unit': 'g'})
        resina_type, _ = MaterialType.objects.get_or_create(name='Resina', defaults={'unit': 'ml'})

        self.stdout.write('Creando materiales y sus unidades (bobina/botella individual)...')
        materials = {}
        units = {}
        type_counters = {'Filamento': 0, 'Resina': 0}

        for m in MATERIALS:
            mtype = filamento_type if m['type'] == 'Filamento' else resina_type
            material, created = Material.objects.get_or_create(
                brand=m['brand'],
                name=m['name'],
                color=m['color'],
                defaults={
                    'material_type': mtype,
                    'business_line': m['line'],
                    'current_stock': 0,
                    'unit_cost': m['cost'],
                },
            )
            if created:
                self.stdout.write(f'  + {material}')
            AlertThreshold.objects.get_or_create(
                material=material,
                defaults={'min_stock': m['min_stock']},
            )

            type_counters[m['type']] += 1
            prefix = 'RES' if m['type'] == 'Resina' else 'FIL'
            code = f"{prefix}-{type_counters[m['type']]:03d}"
            unit, _ = MaterialUnit.objects.get_or_create(
                code=code,
                defaults={
                    'material': material,
                    'sede': sedes[m['sede']],
                    'color': material.color,
                    'finish': 'Silk' if 'Silk' in m['name'] else '',
                    'density': Decimal('1.10'),
                    'nominal_capacity': Decimal('1000'),
                    'status': MaterialUnit.Status.NEW,
                },
            )
            materials[f"{m['brand']}|{m['name']}|{m['color']}"] = material
            units[m['brand'] + '|' + m['name'] + '|' + m['color']] = unit

        self.stdout.write('Registrando compras (la compra acredita el stock en la unidad)...')
        today = timezone.now().date()
        for i, m in enumerate(MATERIALS):
            key = f"{m['brand']}|{m['name']}|{m['color']}"
            purchase_date = today - timedelta(days=20 - i)
            unit = units[key]
            if not StockMovement.objects.filter(
                material_unit=unit,
                adjustment_type=StockMovement.AdjustmentType.PURCHASE,
            ).exists():
                movement = StockMovement.objects.create(
                    material=materials[key],
                    material_unit=unit,
                    movement_type=StockMovement.MovementType.IN,
                    adjustment_type=StockMovement.AdjustmentType.PURCHASE,
                    quantity=m['stock'],
                    reference=f'Compra #INV-00{i+1}',
                    notes=f'Proveedor: {m["brand"]} - compra inicial de stock',
                    created_by=demo_user,
                )
                StockMovement.objects.filter(pk=movement.pk).update(
                    created_at=timezone.make_aware(
                        datetime.combine(purchase_date, datetime.min.time().replace(hour=10))
                    )
                )

        self.stdout.write('Registrando trabajos de impresión (descuentan de la unidad)...')
        for i, (machine, print_name, key) in enumerate(PRINT_JOBS):
            unit = units[key]
            qty = PRINT_CONSUMPTION[i]
            job_date = today - timedelta(days=6 - i)
            if not PrintJob.objects.filter(print_name=print_name).exists():
                job = PrintJob.objects.create(
                    machine=machine,
                    print_name=print_name,
                    laminator_data={
                        'source': 'mock-laminator',
                        'estimated_material_g': qty,
                        'print_time_min': 120 + i * 30,
                    },
                    created_by=demo_user,
                )
                PrintJobItem.objects.create(
                    print_job=job, material_unit=unit, quantity_used=qty,
                )
                job.register_consumption()
                PrintJob.objects.filter(pk=job.pk).update(
                    created_at=timezone.make_aware(
                        datetime.combine(job_date, datetime.min.time().replace(hour=14))
                    )
                )
                self.stdout.write(f'  + Trabajo {print_name} (-{qty}{unit.material.material_type.unit})')

        demo = MULTI_COLOR_JOB
        primary_unit = units[demo['primary']]
        secondary_unit = units[demo['secondary']]
        if not PrintJob.objects.filter(print_name=demo['print_name']).exists():
            job = PrintJob.objects.create(
                machine=demo['machine'],
                print_name=demo['print_name'],
                laminator_data={
                    'source': 'mock-laminator',
                    'estimated_material_g': demo['qty_primary'] + demo['qty_secondary'],
                    'print_time_min': 300,
                    'note': 'Cambio de rollo a mitad del trabajo (2 bobinas)',
                },
                created_by=demo_user,
            )
            PrintJobItem.objects.create(
                print_job=job, material_unit=primary_unit, quantity_used=demo['qty_primary'],
            )
            PrintJobItem.objects.create(
                print_job=job, material_unit=secondary_unit, quantity_used=demo['qty_secondary'],
            )
            job.register_consumption()
            self.stdout.write(
                f'  + Trabajo {demo["print_name"]} '
                f'({primary_unit.code}: -{demo["qty_primary"]}, '
                f'{secondary_unit.code}: -{demo["qty_secondary"]} - cambio de rollo)'
            )

        self.stdout.write(self.style.SUCCESS(
            'Datos de prueba cargados. Usuario demo: demo / demo12345'
        ))
        self.stdout.write(self.style.SUCCESS('Login: POST /api/auth/login/ con demo/demo12345'))
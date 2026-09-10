from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import User
from inventory.models import (
    AlertThreshold,
    Material,
    MaterialType,
    PrintJob,
    StockMovement,
)

MATERIALS = [
    {
        'name': 'PLA Basic', 'type': 'Filamento', 'unit': 'g',
        'brand': 'Bambu Lab', 'color': 'Blanco', 'line': 'PRINT',
        'stock': 1200, 'cost': 89.00, 'min_stock': 250,
    },
    {
        'name': 'PLA Basic', 'type': 'Filamento', 'unit': 'g',
        'brand': 'Bambu Lab', 'color': 'Negro', 'line': 'EDU',
        'stock': 800, 'cost': 89.00, 'min_stock': 300,
    },
    {
        'name': 'PETG', 'type': 'Filamento', 'unit': 'g',
        'brand': 'eSun', 'color': 'Transparente', 'line': 'ICON',
        'stock': 650, 'cost': 99.00, 'min_stock': 200,
    },
    {
        'name': 'PLA Silk', 'type': 'Filamento', 'unit': 'g',
        'brand': 'Creality', 'color': 'Dorado', 'line': 'PRINT',
        'stock': 450, 'cost': 105.00, 'min_stock': 200,
    },
    {
        'name': 'Resina Estándar', 'type': 'Resina', 'unit': 'ml',
        'brand': 'Anycubic', 'color': 'Transparente', 'line': 'TECH',
        'stock': 800, 'cost': 65.00, 'min_stock': 250,
    },
    {
        'name': 'Resina Water-Washable', 'type': 'Resina', 'unit': 'ml',
        'brand': 'Elegoo', 'color': 'Gris', 'line': 'GENERAL',
        'stock': 350, 'cost': 72.00, 'min_stock': 300,
    },
]

PRINT_JOBS = [
    ('Bambu Lab X1C', 'Portavasos ICON #12', 'Bambu Lab|PLA Basic|Blanco'),
    ('Bambu Lab X1C', 'Llaveros EDU - Lote 3', 'Bambu Lab|PLA Basic|Blanco'),
    ('Creality Ender 3', 'Prototipo TECH - Soporte', 'eSun|PETG|Transparente'),
    ('Elegoo Saturn 2', 'Miniatura de exhibición', 'Anycubic|Resina Estándar|Transparente'),
    ('Bambu Lab P1S', 'Figura escala PRINT - Serie 7', 'Creality|PLA Silk|Dorado'),
]

PRINT_CONSUMPTION_G = [45, 57, 69, 81, 93]


class Command(BaseCommand):
    help = 'Carga datos de prueba realistas alineados al rubro de Krea Lab'

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

        self.stdout.write('Creando tipos de material...')
        filamento_type, _ = MaterialType.objects.get_or_create(name='Filamento', defaults={'unit': 'g'})
        resina_type, _ = MaterialType.objects.get_or_create(name='Resina', defaults={'unit': 'ml'})

        self.stdout.write('Creando materiales con stock inicial en 0...')
        materials = {}
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
            materials[f"{m['brand']}|{m['name']}|{m['color']}"] = material

        self.stdout.write('Registrando entradas de compra (la compra acredita el stock)...')
        today = timezone.now().date()
        for i, m in enumerate(MATERIALS):
            key = f"{m['brand']}|{m['name']}|{m['color']}"
            purchase_date = today - timedelta(days=20 - i)
            if not StockMovement.objects.filter(
                material=materials[key],
                adjustment_type=StockMovement.AdjustmentType.PURCHASE,
            ).exists():
                movement = StockMovement.objects.create(
                    material=materials[key],
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

        self.stdout.write('Registrando trabajos de impresión (descuentan stock)...')
        for i, (machine, print_name, key) in enumerate(PRINT_JOBS):
            material = materials[key]
            qty = PRINT_CONSUMPTION_G[i]
            job_date = today - timedelta(days=6 - i)
            if not PrintJob.objects.filter(print_name=print_name).exists():
                job = PrintJob.objects.create(
                    material=material,
                    quantity_used=qty,
                    machine=machine,
                    print_name=print_name,
                    laminator_data={
                        'source': 'mock-laminator',
                        'estimated_material_g': qty,
                        'print_time_min': 120 + i * 30,
                    },
                    created_by=demo_user,
                )
                PrintJob.objects.filter(pk=job.pk).update(
                    created_at=timezone.make_aware(
                        datetime.combine(job_date, datetime.min.time().replace(hour=14))
                    )
                )
                self.stdout.write(f'  + Trabajo {print_name} (-{qty}{material.material_type.unit})')

        self.stdout.write(self.style.SUCCESS(
            'Datos de prueba cargados. Usuario demo: demo / demo12345'
        ))
        self.stdout.write(self.style.SUCCESS('Login: POST /api/auth/login/ con demo/demo12345'))
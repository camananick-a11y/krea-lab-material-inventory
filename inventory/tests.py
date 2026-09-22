from decimal import Decimal
from pathlib import Path

from django.core.management import call_command
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from .models import (
    AlertThreshold,
    Material,
    MaterialType,
    MaterialUnit,
    PrintJob,
    PrintJobItem,
    Sede,
    StockMovement,
)


class BaseAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='operator', password='password123', role=User.Role.OPERATOR,
        )
        self.admin = User.objects.create_user(
            username='admin', password='password123', role=User.Role.ADMIN,
        )
        self.filamento = MaterialType.objects.create(name='Filamento', unit='g')
        self.resina = MaterialType.objects.create(name='Resina', unit='ml')
        self.sede = Sede.objects.create(name='Villa El Salvador', city='Lima')
        self.material = Material.objects.create(
            name='PLA Basic', material_type=self.filamento,
            brand='Bambu Lab', color='Blanco', business_line='PRINT',
            current_stock=0, unit_cost=89,
        )
        self.threshold = AlertThreshold.objects.create(
            material=self.material, min_stock=250,
        )
        self.client.force_authenticate(user=self.user)


class MaterialUnitModelTests(APITestCase):
    def setUp(self):
        filamento = MaterialType.objects.create(name='Filamento', unit='g')
        resina = MaterialType.objects.create(name='Resina', unit='ml')
        self.sede = Sede.objects.create(name='Lince', city='Lima')
        self.f_material = Material.objects.create(
            name='PLA Basic', material_type=filamento,
            brand='Bambu Lab', color='Negro',
        )
        self.r_material = Material.objects.create(
            name='Resina Estándar', material_type=resina,
            brand='Anycubic', color='Transparente',
        )

    _code_counter = 0

    def make_filament_unit(self, gross=1000, empty=0):
        type(self)._code_counter += 1
        return MaterialUnit.objects.create(
            code=f'FIL-T{type(self)._code_counter:02d}', material=self.f_material, sede=self.sede,
            gross_weight=gross, empty_weight=empty,
            nominal_capacity=Decimal('1000'),
        )

    def test_filament_remaining_and_fill_level(self):
        unit = self.make_filament_unit(gross=600)
        self.assertEqual(unit.remaining, Decimal('600'))
        self.assertEqual(unit.percent, Decimal('60'))
        self.assertEqual(unit.fill_level, 'Mitad')

    def test_generate_qr_labels_command(self):
        unit = self.make_filament_unit(gross=600)
        import tempfile
        target = Path(tempfile.mkdtemp()) / 'qr_labels.html'
        call_command(
            'generate_qr_labels',
            '--base-url', 'https://inventario.krea.lab',
            '--output', str(target),
        )
        html = target.read_text(encoding='utf-8')
        self.assertIn(unit.code, html)
        self.assertIn('https://inventario.krea.lab/api/inventory/u/', html)
        self.assertIn('data:image/png;base64', html)
        self.assertNotIn('current_stock', html)

    def test_fill_level_edges(self):
        self.assertEqual(self.make_filament_unit(900).fill_level, 'Lleno')
        self.assertEqual(self.make_filament_unit(700).fill_level, 'Mitad')
        self.assertEqual(self.make_filament_unit(400).fill_level, 'Cuarto')
        self.assertEqual(self.make_filament_unit(100).fill_level, 'Por agotar')

    def test_resin_remaining_uses_density(self):
        unit = MaterialUnit.objects.create(
            code='RES-T01', material=self.r_material, sede=self.sede,
            gross_weight=Decimal('1100'), empty_weight=0,
            density=Decimal('1.10'), nominal_capacity=Decimal('1000'),
        )
        self.assertEqual(unit.remaining, Decimal('1000'))
        self.assertEqual(unit.remaining_weight, Decimal('1100'))
        self.assertEqual(unit.percent, Decimal('100'))
        self.assertEqual(unit.fill_level, 'Lleno')

    def test_status_goes_exhausted_when_empty(self):
        unit = self.make_filament_unit(gross=20)
        unit.adjust_content(Decimal('30'))
        unit.refresh_from_db()
        self.assertEqual(unit.status, MaterialUnit.Status.EXHAUSTED)
        self.assertEqual(unit.gross_weight, Decimal('0'))

    def test_consumption_recalc_material_stock(self):
        unit = self.make_filament_unit(gross=1000)
        unit.adjust_content(Decimal('120'))
        self.f_material.refresh_from_db()
        self.assertEqual(self.f_material.current_stock, Decimal('880'))

    def test_multi_unit_stock_is_sum_of_remaining(self):
        self.make_filament_unit(gross=600)
        self.make_filament_unit(gross=400)
        self.f_material.refresh_from_db()
        self.assertEqual(self.f_material.current_stock, Decimal('1000'))


class StockMovementModelTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='operator', password='password123',
        )
        filamento = MaterialType.objects.create(name='Filamento', unit='g')
        self.sede = Sede.objects.create(name='Villa El Salvador')
        self.material = Material.objects.create(
            name='PLA Basic', material_type=filamento,
            brand='Bambu Lab', color='Blanco', current_stock=1000,
        )

    def test_in_movement_increases_stock(self):
        StockMovement.objects.create(
            material=self.material,
            movement_type=StockMovement.MovementType.IN,
            adjustment_type=StockMovement.AdjustmentType.PURCHASE,
            quantity=500, reference='Compra #001', created_by=self.user,
        )
        self.material.refresh_from_db()
        self.assertEqual(self.material.current_stock, 1500)

    def test_out_movement_without_unit_is_legacy_path(self):
        StockMovement.objects.create(
            material=self.material,
            movement_type=StockMovement.MovementType.OUT,
            adjustment_type=StockMovement.AdjustmentType.PRINT_JOB,
            quantity=150, reference='Trabajo #1', created_by=self.user,
        )
        self.material.refresh_from_db()
        self.assertEqual(self.material.current_stock, 850)

    def test_out_movement_with_unit_discounts_unit(self):
        unit = MaterialUnit.objects.create(
            code='FIL-001', material=self.material, sede=self.sede,
            gross_weight=1000,
        )
        StockMovement.objects.create(
            material=self.material, material_unit=unit,
            movement_type=StockMovement.MovementType.OUT,
            adjustment_type=StockMovement.AdjustmentType.PRINT_JOB,
            quantity=40, reference='Trabajo #7', created_by=self.user,
        )
        unit.refresh_from_db()
        self.material.refresh_from_db()
        self.assertEqual(unit.remaining, 960)
        self.assertEqual(self.material.current_stock, 960)

    def test_out_movement_rejects_insufficient_unit_stock(self):
        unit = MaterialUnit.objects.create(
            code='FIL-002', material=self.material, sede=self.sede,
            gross_weight=50,
        )
        with self.assertRaises(Exception):
            StockMovement.objects.create(
                material=self.material, material_unit=unit,
                movement_type=StockMovement.MovementType.OUT,
                adjustment_type=StockMovement.AdjustmentType.PRINT_JOB,
                quantity=100, created_by=self.user,
            )
        unit.refresh_from_db()
        self.assertEqual(unit.remaining, 50)

    def test_resin_out_movement_uses_ml_and_density(self):
        resina = MaterialType.objects.create(name='Resina', unit='ml')
        material = Material.objects.create(
            name='Resina Estándar', material_type=resina,
            brand='Anycubic', color='Gris',
        )
        unit = MaterialUnit.objects.create(
            code='RES-001', material=material, sede=self.sede,
            gross_weight=Decimal('1100'), density=Decimal('1.10'),
        )
        StockMovement.objects.create(
            material=material, material_unit=unit,
            movement_type=StockMovement.MovementType.OUT,
            adjustment_type=StockMovement.AdjustmentType.PRINT_JOB,
            quantity=100, reference='Trabajo resina', created_by=self.user,
        )
        unit.refresh_from_db()
        self.assertEqual(unit.gross_weight, Decimal('990'))
        self.assertEqual(unit.remaining, Decimal('900'))


class PrintJobModelTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='operator', password='password123',
        )
        filamento = MaterialType.objects.create(name='Filamento', unit='g')
        self.sede = Sede.objects.create(name='Villa El Salvador')
        self.material = Material.objects.create(
            name='PETG', material_type=filamento,
            brand='eSun', color='Transparente',
        )
        self.unit = MaterialUnit.objects.create(
            code='FIL-100', material=self.material, sede=self.sede,
            gross_weight=1000,
        )

    def test_print_job_with_single_unit_creates_out_movement(self):
        job = PrintJob.objects.create(
            machine='Bambu Lab X1C', print_name='Soporte TECH',
            created_by=self.user,
        )
        PrintJobItem.objects.create(
            print_job=job, material_unit=self.unit, quantity_used=65,
        )
        job.register_consumption()
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.remaining, 935)
        movements = StockMovement.objects.filter(material_unit=self.unit)
        self.assertEqual(movements.count(), 1)
        self.assertEqual(movements.first().quantity, 65)
        self.assertEqual(movements.first().movement_type, StockMovement.MovementType.OUT)

    def test_print_job_with_two_units_roll_change(self):
        other_material = Material.objects.create(
            name='PLA Silk', material_type=self.material.material_type,
            brand='Creality', color='Dorado',
        )
        other_unit = MaterialUnit.objects.create(
            code='FIL-101', material=other_material, sede=self.sede,
            gross_weight=500,
        )
        job = PrintJob.objects.create(
            machine='Bambu Lab P1S', print_name='Caja 2 colores',
            created_by=self.user,
        )
        PrintJobItem.objects.create(
            print_job=job, material_unit=self.unit, quantity_used=110,
        )
        PrintJobItem.objects.create(
            print_job=job, material_unit=other_unit, quantity_used=40,
        )
        job.register_consumption()
        self.unit.refresh_from_db()
        other_unit.refresh_from_db()
        self.assertEqual(self.unit.remaining, 890)
        self.assertEqual(other_unit.remaining, 460)
        self.assertEqual(StockMovement.objects.filter(material_unit=self.unit).count(), 1)
        self.assertEqual(StockMovement.objects.filter(material_unit=other_unit).count(), 1)


class MaterialAPITests(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.unit = MaterialUnit.objects.create(
            code='FIL-001', material=self.material, sede=self.sede,
            color=self.material.color, gross_weight=1000,
        )

    def test_list_materials_requires_auth(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(reverse('material-list'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_materials_returns_stock_units_and_threshold(self):
        response = self.client.get(reverse('material-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        material = response.data[0]
        self.assertEqual(str(material['current_stock']), '1000.000')
        self.assertFalse(material['is_below_threshold'])
        self.assertEqual(material['units'][0]['code'], 'FIL-001')
        self.assertEqual(material['units'][0]['fill_level'], 'Lleno')

    def test_create_material(self):
        response = self.client.post(reverse('material-list'), {
            'name': 'Resina Estándar', 'material_type': self.resina.id,
            'brand': 'Anycubic', 'color': 'Transparente',
            'business_line': 'TECH', 'current_stock': 500, 'unit_cost': 65,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Material.objects.count(), 2)

    def test_low_stock_endpoint_flags_material_below_threshold(self):
        response = self.client.get(reverse('material-low-stock'))
        self.assertEqual(response.data, [])

        self.client.patch(
            reverse('threshold-detail', args=[self.threshold.id]),
            {'min_stock': '2000'}, format='json',
        )
        response = self.client.get(reverse('material-low-stock'))
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], self.material.id)

    def test_units_low_endpoint_flags_depleted_level(self):
        MaterialUnit.objects.create(
            code='FIL-002', material=self.material, sede=self.sede,
            gross_weight=100,
        )
        response = self.client.get(reverse('unit-low'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        codes = [unit['code'] for unit in response.data]
        self.assertIn('FIL-002', codes)
        self.assertNotIn('FIL-001', codes)

    def test_brands_endpoint_groups_materials_by_brand(self):
        response = self.client.get(reverse('brand-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]['name'], 'Bambu Lab')
        self.assertEqual(response.data[0]['materials_count'], 1)


class UnitPublicEndpointTests(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.unit = MaterialUnit.objects.create(
            code='FIL-001', material=self.material, sede=self.sede,
            color=self.material.color, finish='Silk',
            hex_color='#1A1A1A', gross_weight=800,
        )

    def test_public_endpoint_anonymous_returns_minimal_card(self):
        anon = self.client.__class__()
        response = anon.get(reverse('unit-public', kwargs={'code': 'FIL-001'}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['code'], 'FIL-001')
        self.assertIn('material_name', response.data)
        self.assertNotIn('gross_weight', response.data)
        self.assertNotIn('remaining', response.data)
        self.assertNotIn('unit_cost', response.data)

    def test_public_endpoint_authenticated_returns_full_data(self):
        response = self.client.get(reverse('unit-public', kwargs={'code': 'FIL-001'}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('remaining', response.data)
        self.assertIn('gross_weight', response.data)

    def test_public_endpoint_unknown_code_404(self):
        anon = self.client.__class__()
        response = anon.get(reverse('unit-public', kwargs={'code': 'FIL-999'}))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class StockMovementAPITests(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.unit = MaterialUnit.objects.create(
            code='FIL-001', material=self.material, sede=self.sede,
            gross_weight=1000,
        )

    def test_create_out_movement_with_unit_discounts_stock(self):
        response = self.client.post(reverse('movement-list'), {
            'material': self.material.id,
            'material_unit': self.unit.id,
            'movement_type': 'OUT',
            'adjustment_type': 'print_job',
            'quantity': 40,
            'reference': 'Trabajo #7',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['created_by'], self.user.id)
        self.unit.refresh_from_db()
        self.material.refresh_from_db()
        self.assertEqual(self.unit.remaining, 960)
        self.assertEqual(self.material.current_stock, 960)

    def test_create_out_movement_unit_insufficient_is_rejected(self):
        response = self.client.post(reverse('movement-list'), {
            'material': self.material.id,
            'material_unit': self.unit.id,
            'movement_type': 'OUT',
            'adjustment_type': 'print_job',
            'quantity': 5000,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.remaining, 1000)

    def test_create_print_job_with_items_via_api(self):
        response = self.client.post(reverse('print-job-list'), {
            'machine': 'Bambu Lab X1C',
            'print_name': 'Portavasos #13',
            'items': [
                {'material_unit': self.unit.id, 'quantity_used': 33},
            ],
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['items'][0]['material_unit_code'], 'FIL-001')
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.remaining, 967)
        self.assertEqual(StockMovement.objects.filter(material_unit=self.unit).count(), 1)
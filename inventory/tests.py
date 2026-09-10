from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from .models import (
    AlertThreshold,
    Material,
    MaterialType,
    PrintJob,
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
        self.material = Material.objects.create(
            name='PLA Basic', material_type=self.filamento,
            brand='Bambu Lab', color='Blanco', business_line='PRINT',
            current_stock=1000, unit_cost=89,
        )
        self.threshold = AlertThreshold.objects.create(
            material=self.material, min_stock=250,
        )
        self.client.force_authenticate(user=self.user)


class StockMovementModelTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='operator', password='password123',
        )
        filamento = MaterialType.objects.create(name='Filamento', unit='g')
        self.material = Material.objects.create(
            name='PLA Basic', material_type=filamento,
            brand='Bambu Lab', color='Negro', current_stock=1000,
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

    def test_out_movement_decreases_stock(self):
        StockMovement.objects.create(
            material=self.material,
            movement_type=StockMovement.MovementType.OUT,
            adjustment_type=StockMovement.AdjustmentType.PRINT_JOB,
            quantity=150, reference='Trabajo #1', created_by=self.user,
        )
        self.material.refresh_from_db()
        self.assertEqual(self.material.current_stock, 850)

    def test_out_movement_rejects_insufficient_stock(self):
        with self.assertRaises(Exception):
            StockMovement.objects.create(
                material=self.material,
                movement_type=StockMovement.MovementType.OUT,
                adjustment_type=StockMovement.AdjustmentType.PRINT_JOB,
                quantity=9999, created_by=self.user,
            )
        self.material.refresh_from_db()
        self.assertEqual(self.material.current_stock, 1000)

    def test_chain_of_movements_is_consistent(self):
        StockMovement.objects.create(
            material=self.material, movement_type=StockMovement.MovementType.IN,
            adjustment_type=StockMovement.AdjustmentType.PURCHASE,
            quantity=300, created_by=self.user,
        )
        StockMovement.objects.create(
            material=self.material, movement_type=StockMovement.MovementType.OUT,
            adjustment_type=StockMovement.AdjustmentType.PRINT_JOB,
            quantity=120, created_by=self.user,
        )
        StockMovement.objects.create(
            material=self.material, movement_type=StockMovement.MovementType.OUT,
            adjustment_type=StockMovement.AdjustmentType.WASTE,
            quantity=30, created_by=self.user,
        )
        self.material.refresh_from_db()
        self.assertEqual(self.material.current_stock, 1000 + 300 - 120 - 30)


class PrintJobModelTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='operator', password='password123',
        )
        filamento = MaterialType.objects.create(name='Filamento', unit='g')
        self.material = Material.objects.create(
            name='PETG', material_type=filamento,
            brand='eSun', color='Transparente', current_stock=650,
        )

    def test_print_job_creates_automatic_out_movement(self):
        PrintJob.objects.create(
            material=self.material, quantity_used=65,
            machine='Creality Ender 3', print_name='Soporte TECH',
            created_by=self.user,
        )
        self.material.refresh_from_db()
        self.assertEqual(self.material.current_stock, 585)
        out_movements = StockMovement.objects.filter(
            material=self.material,
            adjustment_type=StockMovement.AdjustmentType.PRINT_JOB,
        )
        self.assertEqual(out_movements.count(), 1)
        self.assertEqual(out_movements.first().quantity, 65)
        self.assertEqual(out_movements.first().movement_type, StockMovement.MovementType.OUT)


class MaterialAPITests(BaseAPITest):
    def test_list_materials_requires_auth(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(reverse('material-list'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_materials_returns_stock_and_threshold(self):
        response = self.client.get(reverse('material-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        material = response.data[0]
        self.assertEqual(str(material['current_stock']), '1000.000')
        self.assertFalse(material['is_below_threshold'])

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


class StockMovementAPITests(BaseAPITest):
    def test_create_out_movement_discounts_stock(self):
        response = self.client.post(reverse('movement-list'), {
            'material': self.material.id,
            'movement_type': 'OUT',
            'adjustment_type': 'print_job',
            'quantity': 40,
            'reference': 'Trabajo #7',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['created_by'], self.user.id)
        self.material.refresh_from_db()
        self.assertEqual(self.material.current_stock, 960)

    def test_create_out_movement_with_insufficient_stock_is_rejected(self):
        response = self.client.post(reverse('movement-list'), {
            'material': self.material.id,
            'movement_type': 'OUT',
            'adjustment_type': 'print_job',
            'quantity': 5000,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.material.refresh_from_db()
        self.assertEqual(self.material.current_stock, 1000)

    def test_create_print_job_creates_movement_via_api(self):
        response = self.client.post(reverse('print-job-list'), {
            'material': self.material.id,
            'quantity_used': 33,
            'machine': 'Bambu Lab X1C',
            'print_name': 'Llavero EDU',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.material.refresh_from_db()
        self.assertEqual(self.material.current_stock, 967)
        self.assertEqual(StockMovement.objects.filter(material=self.material).count(), 1)
from datetime import date, timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from inventory.models import Material, MaterialType, StockMovement


class ConsumptionReportTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='operator', password='password123',
        )
        filamento = MaterialType.objects.create(name='Filamento', unit='g')
        self.material_a = Material.objects.create(
            name='PLA Basic', material_type=filamento,
            brand='Bambu Lab', color='Blanco', current_stock=1000,
        )
        self.material_b = Material.objects.create(
            name='PETG', material_type=filamento,
            brand='eSun', color='Transparente', current_stock=1000,
        )
        self.client.force_authenticate(user=self.user)

    def _create_out(self, material, qty, days_ago=0):
        movement = StockMovement.objects.create(
            material=material,
            movement_type=StockMovement.MovementType.OUT,
            adjustment_type=StockMovement.AdjustmentType.PRINT_JOB,
            quantity=qty, created_by=self.user,
        )
        StockMovement.objects.filter(pk=movement.pk).update(
            created_at=timezone.now() - timedelta(days=days_ago)
        )
        return movement

    def test_report_totals_consumption_by_material(self):
        self._create_out(self.material_a, 50)
        self._create_out(self.material_a, 30)
        self._create_out(self.material_b, 20)

        response = self.client.get(reverse('consumption-report'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(float(response.data['total_out_quantity']), 100)
        self.assertEqual(response.data['total_movements'], 3)
        rows = {row['material_id']: float(row['quantity']) for row in response.data['rows']}
        self.assertEqual(rows[self.material_a.id], 80)
        self.assertEqual(rows[self.material_b.id], 20)

    def test_report_filters_by_material(self):
        self._create_out(self.material_a, 50)
        self._create_out(self.material_b, 20)

        response = self.client.get(
            reverse('consumption-report'), {'material': self.material_a.id},
        )
        self.assertEqual(float(response.data['total_out_quantity']), 50)
        self.assertEqual(len(response.data['rows']), 1)
        self.assertEqual(response.data['rows'][0]['material_id'], self.material_a.id)

    def test_report_filters_by_period(self):
        self._create_out(self.material_a, 50, days_ago=10)
        self._create_out(self.material_a, 30, days_ago=2)

        today = date.today()
        response = self.client.get(reverse('consumption-report'), {
            'from': (today - timedelta(days=7)).isoformat(),
            'to': today.isoformat(),
        })
        self.assertEqual(float(response.data['total_out_quantity']), 30)
        self.assertEqual(response.data['total_movements'], 1)

    def test_report_ignores_inbound_movements(self):
        StockMovement.objects.create(
            material=self.material_a,
            movement_type=StockMovement.MovementType.IN,
            adjustment_type=StockMovement.AdjustmentType.PURCHASE,
            quantity=500, created_by=self.user,
        )
        self._create_out(self.material_a, 40)

        response = self.client.get(reverse('consumption-report'))
        self.assertEqual(float(response.data['total_out_quantity']), 40)
        self.assertEqual(response.data['total_movements'], 1)

    def test_summary_reports_low_stock(self):
        from inventory.models import AlertThreshold
        AlertThreshold.objects.create(material=self.material_a, min_stock=2000)

        response = self.client.get(reverse('summary'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_materials'], 2)
        self.assertEqual(response.data['low_stock_count'], 1)
        self.assertEqual(response.data['low_stock'][0]['id'], self.material_a.id)
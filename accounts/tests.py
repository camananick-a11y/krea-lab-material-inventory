from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import User


class AuthAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='demo', password='demo12345', role=User.Role.ADMIN,
        )

    def test_login_returns_access_refresh_and_user(self):
        response = self.client.post(reverse('login'), {
            'username': 'demo', 'password': 'demo12345',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertEqual(response.data['user']['username'], 'demo')
        self.assertEqual(response.data['user']['role'], 'admin')

    def test_login_wrong_password_rejected(self):
        response = self.client.post(reverse('login'), {
            'username': 'demo', 'password': 'incorrecta',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_register_creates_operator_by_default(self):
        response = self.client.post(reverse('register'), {
            'username': 'nuevo', 'password': 'password123',
            'email': 'nuevo@krea.lab',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username='nuevo')
        self.assertEqual(user.role, User.Role.OPERATOR)

    def test_profile_requires_authentication(self):
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_profile_returns_own_data(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'demo')
        self.assertEqual(response.data['role'], 'admin')

    def test_profile_can_be_updated(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.patch(reverse('profile'), {'phone': '+51 900 000 111'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone, '+51 900 000 111')
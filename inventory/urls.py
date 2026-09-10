from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    AlertThresholdViewSet,
    MaterialTypeViewSet,
    MaterialViewSet,
    PrintJobViewSet,
    StockMovementViewSet,
)

router = DefaultRouter()
router.register('materials', MaterialViewSet, basename='material')
router.register('material-types', MaterialTypeViewSet, basename='material-type')
router.register('thresholds', AlertThresholdViewSet, basename='threshold')
router.register('movements', StockMovementViewSet, basename='movement')
router.register('print-jobs', PrintJobViewSet, basename='print-job')

urlpatterns = [
    path('', include(router.urls)),
]
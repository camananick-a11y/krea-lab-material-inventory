from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    AlertThresholdViewSet,
    BrandViewSet,
    MaterialTypeViewSet,
    MaterialUnitViewSet,
    MaterialViewSet,
    PrintJobViewSet,
    SedeViewSet,
    StockMovementViewSet,
    UnitPublicView,
)

router = DefaultRouter()
router.register('materials', MaterialViewSet, basename='material')
router.register('material-types', MaterialTypeViewSet, basename='material-type')
router.register('brands', BrandViewSet, basename='brand')
router.register('sedes', SedeViewSet, basename='sede')
router.register('units', MaterialUnitViewSet, basename='unit')
router.register('thresholds', AlertThresholdViewSet, basename='threshold')
router.register('movements', StockMovementViewSet, basename='movement')
router.register('print-jobs', PrintJobViewSet, basename='print-job')

urlpatterns = [
    path('', include(router.urls)),
    path('u/<str:code>/', UnitPublicView.as_view(), name='unit-public'),
]
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import (
    AlertThreshold,
    Material,
    MaterialType,
    PrintJob,
    StockMovement,
)
from .serializers import (
    AlertThresholdSerializer,
    MaterialSerializer,
    MaterialTypeSerializer,
    PrintJobSerializer,
    StockMovementSerializer,
)


class MaterialTypeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MaterialType.objects.all()
    serializer_class = MaterialTypeSerializer


class MaterialViewSet(viewsets.ModelViewSet):
    queryset = Material.objects.select_related('material_type').all()
    serializer_class = MaterialSerializer
    search_fields = ('name', 'brand', 'color')
    filterset_fields = ('material_type', 'business_line', 'brand')

    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        below = []
        for material in self.get_queryset():
            threshold = AlertThreshold.objects.filter(material=material).first()
            if threshold and material.current_stock < threshold.min_stock:
                below.append(self.get_serializer(material).data)
        return Response(below)


class AlertThresholdViewSet(viewsets.ModelViewSet):
    queryset = AlertThreshold.objects.select_related('material').all()
    serializer_class = AlertThresholdSerializer


class StockMovementViewSet(viewsets.ModelViewSet):
    queryset = StockMovement.objects.select_related('material', 'created_by').all()
    serializer_class = StockMovementSerializer
    search_fields = ('reference', 'notes')
    filterset_fields = ('material', 'movement_type', 'adjustment_type')


class PrintJobViewSet(viewsets.ModelViewSet):
    queryset = PrintJob.objects.select_related('material', 'created_by').all()
    serializer_class = PrintJobSerializer
    search_fields = ('print_name', 'machine')
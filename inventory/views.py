from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    AlertThreshold,
    Material,
    MaterialType,
    MaterialUnit,
    PrintJob,
    Sede,
    StockMovement,
)
from .serializers import (
    AlertThresholdSerializer,
    MaterialSerializer,
    MaterialTypeSerializer,
    MaterialUnitSerializer,
    PrintJobSerializer,
    SedeSerializer,
    StockMovementSerializer,
    UnitPublicSerializer,
)


class MaterialTypeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MaterialType.objects.all()
    serializer_class = MaterialTypeSerializer


class SedeViewSet(viewsets.ModelViewSet):
    queryset = Sede.objects.all()
    serializer_class = SedeSerializer


class MaterialViewSet(viewsets.ModelViewSet):
    queryset = Material.objects.select_related('material_type').prefetch_related('units').all()
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


class MaterialUnitViewSet(viewsets.ModelViewSet):
    queryset = MaterialUnit.objects.select_related(
        'material', 'material__material_type', 'sede',
    ).prefetch_related('movements')
    serializer_class = MaterialUnitSerializer
    search_fields = ('code', 'material__name', 'material__brand', 'color', 'finish')
    filterset_fields = ('material', 'sede', 'status')

    @action(detail=False, methods=['get'])
    def low(self, request):
        low_units = [u for u in self.get_queryset() if u.fill_level == 'Por agotar']
        return Response(self.get_serializer(low_units, many=True).data)


class BrandViewSet(viewsets.ViewSet):
    """Catálogo dinámico de marcas, derivado de los materiales registrados."""

    def list(self, request):
        brands = (
            Material.objects.values('brand')
            .order_by('brand')
            .distinct()
        )
        rows = []
        for item in brands:
            name = item['brand']
            materials = Material.objects.filter(brand=name)
            rows.append({
                'name': name,
                'materials_count': materials.count(),
                'total_stock': str(sum(m.current_stock for m in materials)),
                'materials': [{
                    'id': m.id,
                    'name': m.name,
                    'color': m.color,
                    'unit': m.material_type.unit,
                    'stock': str(m.current_stock),
                    'business_line': m.business_line,
                } for m in materials],
            })
        return Response(rows)

    def retrieve(self, request, pk=None):
        name = pk
        materials = Material.objects.filter(brand=name)
        if not materials.exists():
            return Response(
                {'detail': 'Marca no encontrada.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({
            'name': name,
            'materials_count': materials.count(),
            'total_stock': str(sum(m.current_stock for m in materials)),
            'materials': [{
                'id': m.id,
                'name': m.name,
                'color': m.color,
                'unit': m.material_type.unit,
                'stock': str(m.current_stock),
                'business_line': m.business_line,
            } for m in materials],
        })


class UnitPublicView(APIView):
    """Ficha de la unidad accesible por su código (etiqueta/QR).

    Anónimo: tarjeta mínima (sin stock ni costos).
    Autenticado: ficha completa del personal.
    """
    permission_classes = [AllowAny]

    def get(self, request, code):
        unit = get_object_or_404(MaterialUnit, code=code)
        if request.user.is_authenticated:
            serializer = MaterialUnitSerializer(unit)
        else:
            serializer = UnitPublicSerializer(unit)
        return Response(serializer.data)


class AlertThresholdViewSet(viewsets.ModelViewSet):
    queryset = AlertThreshold.objects.select_related('material').all()
    serializer_class = AlertThresholdSerializer


class StockMovementViewSet(viewsets.ModelViewSet):
    queryset = StockMovement.objects.select_related(
        'material', 'material_unit', 'created_by',
    ).all()
    serializer_class = StockMovementSerializer
    search_fields = ('reference', 'notes')
    filterset_fields = ('material', 'material_unit', 'movement_type', 'adjustment_type')


class PrintJobViewSet(viewsets.ModelViewSet):
    queryset = PrintJob.objects.prefetch_related(
        'items', 'items__material_unit', 'items__material_unit__material',
    ).all()
    serializer_class = PrintJobSerializer
    search_fields = ('print_name', 'machine')
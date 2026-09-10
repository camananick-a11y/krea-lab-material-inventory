from django.db.models import F, Sum
from drf_spectacular.openapi import OpenApiParameter
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.response import Response

from inventory.models import AlertThreshold, Material, StockMovement

from .serializers import (
    ConsumptionResponseSerializer,
    SummaryResponseSerializer,
)


class ConsumptionReportViewSet(viewsets.ViewSet):
    @extend_schema(
        parameters=[
            OpenApiParameter('material', int, required=False),
            OpenApiParameter('from', str, required=False),
            OpenApiParameter('to', str, required=False),
        ],
        responses=ConsumptionResponseSerializer,
    )
    def list(self, request):
        material_id = request.query_params.get('material')
        from_date = request.query_params.get('from')
        to_date = request.query_params.get('to')

        movements = StockMovement.objects.filter(
            movement_type=StockMovement.MovementType.OUT
        ).select_related('material')
        if material_id:
            movements = movements.filter(material_id=material_id)
        if from_date:
            movements = movements.filter(created_at__date__gte=from_date)
        if to_date:
            movements = movements.filter(created_at__date__lte=to_date)

        rows = (
            movements
            .values('material_id')
            .annotate(
                name=F('material__name'),
                brand=F('material__brand'),
                unit=F('material__material_type__unit'),
                quantity=Sum('quantity'),
            )
            .order_by('-quantity')
        )

        total_quantity = movements.aggregate(total=Sum('quantity'))['total'] or 0
        movements_count = movements.count()

        return Response({
            'filters': {
                'material': material_id,
                'from': from_date,
                'to': to_date,
            },
            'total_out_quantity': str(total_quantity),
            'total_movements': movements_count,
            'rows': list(rows),
        })


class SummaryViewSet(viewsets.ViewSet):
    @extend_schema(responses=SummaryResponseSerializer)
    def list(self, request):
        total_materials = Material.objects.count()
        low_stock = []
        for material in Material.objects.all():
            threshold = AlertThreshold.objects.filter(material=material).first()
            if threshold and material.current_stock < threshold.min_stock:
                low_stock.append({
                    'material': str(material),
                    'id': material.id,
                    'current_stock': str(material.current_stock),
                    'min_stock': str(threshold.min_stock),
                })
        return Response({
            'total_materials': total_materials,
            'low_stock_count': len(low_stock),
            'low_stock': low_stock,
        })
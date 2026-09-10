from rest_framework import serializers

from .models import (
    AlertThreshold,
    Material,
    MaterialType,
    PrintJob,
    StockMovement,
)


class MaterialTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaterialType
        fields = ('id', 'name', 'unit')


class AlertThresholdSerializer(serializers.ModelSerializer):
    material_name = serializers.CharField(source='material.__str__', read_only=True)

    class Meta:
        model = AlertThreshold
        fields = ('id', 'material', 'material_name', 'min_stock', 'notify_email', 'updated_at')
        read_only_fields = ('updated_at',)


class MaterialSerializer(serializers.ModelSerializer):
    material_type_name = serializers.CharField(source='material_type.__str__', read_only=True)
    threshold = AlertThresholdSerializer(read_only=True)
    is_below_threshold = serializers.SerializerMethodField()

    class Meta:
        model = Material
        fields = (
            'id', 'name', 'material_type', 'material_type_name',
            'brand', 'color', 'business_line',
            'current_stock', 'unit_cost', 'is_below_threshold',
            'threshold', 'created_at', 'updated_at',
        )
        read_only_fields = ('created_at', 'updated_at')

    def get_is_below_threshold(self, obj) -> bool:
        return obj.is_below_threshold


class StockMovementSerializer(serializers.ModelSerializer):
    material_name = serializers.CharField(source='material.__str__', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = StockMovement
        fields = (
            'id', 'material', 'material_name', 'movement_type',
            'adjustment_type', 'quantity', 'reference', 'notes',
            'created_by', 'created_by_name', 'created_at',
        )
        read_only_fields = ('created_by', 'created_at')

    def validate(self, attrs):
        movement_type = attrs.get('movement_type', getattr(self.instance, 'movement_type', None))
        quantity = attrs.get('quantity', getattr(self.instance, 'quantity', None))
        if movement_type == StockMovement.MovementType.OUT and quantity:
            material = attrs.get('material', getattr(self.instance, 'material', None))
            if material and material.current_stock < quantity:
                raise serializers.ValidationError(
                    f'Stock insuficiente del material {material}: '
                    f'disponible {material.current_stock}, solicitado {quantity}.'
                )
        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['created_by'] = request.user
        return super().create(validated_data)


class PrintJobSerializer(serializers.ModelSerializer):
    material_name = serializers.CharField(source='material.__str__', read_only=True)

    class Meta:
        model = PrintJob
        fields = (
            'id', 'material', 'material_name', 'quantity_used',
            'machine', 'print_name', 'laminator_data',
            'created_by', 'created_at',
        )
        read_only_fields = ('created_by', 'created_at')

    def create(self, validated_data):
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['created_by'] = request.user
        return super().create(validated_data)
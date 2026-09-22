from rest_framework import serializers

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


class MaterialTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaterialType
        fields = ('id', 'name', 'unit')


class SedeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sede
        fields = ('id', 'name', 'address', 'city', 'is_active')


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
    units = serializers.SerializerMethodField()

    class Meta:
        model = Material
        fields = (
            'id', 'name', 'material_type', 'material_type_name',
            'brand', 'color', 'business_line',
            'current_stock', 'unit_cost', 'is_below_threshold',
            'threshold', 'units', 'created_at', 'updated_at',
        )
        read_only_fields = ('created_at', 'updated_at')

    def get_is_below_threshold(self, obj) -> bool:
        return obj.is_below_threshold

    def get_units(self, obj):
        return [{
            'code': u.code,
            'remaining': str(u.remaining),
            'unit': obj.material_type.unit,
            'fill_level': u.fill_level,
            'status': u.status,
            'sede': u.sede.name if u.sede else None,
            'qr_url': u.qr_url,
        } for u in obj.units.all()]


class MaterialUnitSerializer(serializers.ModelSerializer):
    material_name = serializers.CharField(source='material.name', read_only=True)
    brand = serializers.CharField(source='material.brand', read_only=True)
    material_type = serializers.CharField(source='material.material_type.name', read_only=True)
    unit = serializers.CharField(source='material.material_type.unit', read_only=True)
    business_line = serializers.CharField(source='material.business_line', read_only=True)
    sede_name = serializers.CharField(source='sede.name', read_only=True)
    remaining_weight = serializers.SerializerMethodField()
    remaining = serializers.SerializerMethodField()
    percent = serializers.SerializerMethodField()
    fill_level = serializers.SerializerMethodField()
    qr_url = serializers.ReadOnlyField()

    class Meta:
        model = MaterialUnit
        fields = (
            'id', 'code', 'material', 'material_name', 'brand',
            'material_type', 'unit', 'business_line',
            'finish', 'color', 'hex_color', 'photo_ref',
            'sede', 'sede_name', 'status', 'fill_level',
            'gross_weight', 'empty_weight', 'density', 'nominal_capacity',
            'remaining_weight', 'remaining', 'percent',
            'qr_url', 'created_at', 'updated_at',
        )
        read_only_fields = ('created_at', 'updated_at')

    def get_remaining_weight(self, obj):
        return str(obj.remaining_weight)

    def get_remaining(self, obj):
        return str(obj.remaining)

    def get_percent(self, obj):
        return str(obj.percent)

    def get_fill_level(self, obj):
        return obj.fill_level


class UnitPublicSerializer(serializers.ModelSerializer):
    """Tarjeta mínima que ve quien escanea el QR sin sesión (sin stock ni costos)."""

    material_name = serializers.CharField(source='material.name', read_only=True)
    brand = serializers.CharField(source='material.brand', read_only=True)
    material_type = serializers.CharField(source='material.material_type.name', read_only=True)
    unit = serializers.CharField(source='material.material_type.unit', read_only=True)
    business_line = serializers.CharField(source='material.business_line', read_only=True)
    sede_name = serializers.CharField(source='sede.name', read_only=True)
    qr_url = serializers.ReadOnlyField()

    class Meta:
        model = MaterialUnit
        fields = (
            'code', 'material_name', 'brand', 'material_type', 'unit',
            'business_line', 'finish', 'color', 'hex_color', 'photo_ref',
            'status', 'fill_level', 'sede_name', 'qr_url',
        )


class StockMovementSerializer(serializers.ModelSerializer):
    material_name = serializers.CharField(source='material.__str__', read_only=True)
    material_unit_code = serializers.CharField(source='material_unit.code', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = StockMovement
        fields = (
            'id', 'material', 'material_name', 'material_unit',
            'material_unit_code', 'movement_type', 'adjustment_type',
            'quantity', 'reference', 'notes',
            'created_by', 'created_by_name', 'created_at',
        )
        read_only_fields = ('created_by', 'created_at')

    def validate(self, attrs):
        movement_type = attrs.get('movement_type', getattr(self.instance, 'movement_type', None))
        quantity = attrs.get('quantity', getattr(self.instance, 'quantity', None))
        material_unit = attrs.get('material_unit', getattr(self.instance, 'material_unit', None))
        material = attrs.get('material', getattr(self.instance, 'material', None))

        if movement_type == StockMovement.MovementType.OUT and quantity:
            if material_unit:
                if material_unit.remaining < quantity:
                    raise serializers.ValidationError(
                        f'Stock insuficiente en {material_unit.code}: '
                        f'disponible {material_unit.remaining}, solicitado {quantity}.'
                    )
            elif material and material.current_stock < quantity:
                raise serializers.ValidationError(
                    f'Stock insuficiente del material {material}: '
                    f'disponible {material.current_stock}, solicitado {quantity}.'
                )
        if material_unit:
            attrs['material'] = material_unit.material
        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['created_by'] = request.user
        return super().create(validated_data)


class PrintJobItemSerializer(serializers.ModelSerializer):
    material_unit_code = serializers.CharField(source='material_unit.code', read_only=True)
    material_name = serializers.CharField(source='material_unit.material.__str__', read_only=True)

    class Meta:
        model = PrintJobItem
        fields = ('id', 'material_unit', 'material_unit_code', 'material_name', 'quantity_used')


class PrintJobSerializer(serializers.ModelSerializer):
    items = PrintJobItemSerializer(many=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = PrintJob
        fields = (
            'id', 'machine', 'print_name', 'laminator_data', 'items',
            'created_by', 'created_by_name', 'created_at',
        )
        read_only_fields = ('created_by', 'created_at')

    def create(self, validated_data):
        items = validated_data.pop('items', [])
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['created_by'] = request.user
        job = PrintJob.objects.create(**validated_data)
        for item_data in items:
            PrintJobItem.objects.create(print_job=job, **item_data)
        job.register_consumption()
        return job
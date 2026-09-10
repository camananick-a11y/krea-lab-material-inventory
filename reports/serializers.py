from rest_framework import serializers


class ConsumptionRowSerializer(serializers.Serializer):
    material_id = serializers.IntegerField()
    name = serializers.CharField()
    brand = serializers.CharField()
    quantity = serializers.FloatField()
    unit = serializers.CharField()


class ConsumptionResponseSerializer(serializers.Serializer):
    filters = serializers.DictField(allow_null=True)
    total_out_quantity = serializers.CharField()
    total_movements = serializers.IntegerField()
    rows = ConsumptionRowSerializer(many=True)


class SummaryResponseSerializer(serializers.Serializer):
    total_materials = serializers.IntegerField()
    low_stock_count = serializers.IntegerField()
    low_stock = serializers.ListField()
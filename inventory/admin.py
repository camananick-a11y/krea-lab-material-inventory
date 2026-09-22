from django.contrib import admin

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


@admin.register(Sede)
class SedeAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'is_active')
    search_fields = ('name', 'city')


@admin.register(MaterialType)
class MaterialTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'unit')


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ('name', 'brand', 'color', 'material_type', 'current_stock', 'business_line')
    list_filter = ('material_type', 'business_line', 'brand')
    search_fields = ('name', 'brand', 'color')


@admin.register(MaterialUnit)
class MaterialUnitAdmin(admin.ModelAdmin):
    list_display = ('code', 'material', 'sede', 'color', 'finish', 'status', 'fill_level', 'remaining_weight', 'percent', 'qr_url')
    list_filter = ('status', 'sede', 'material__material_type')
    search_fields = ('code', 'material__name', 'material__brand', 'color')
    readonly_fields = ('created_at', 'updated_at', 'remaining_weight', 'remaining', 'percent', 'fill_level')


@admin.register(AlertThreshold)
class AlertThresholdAdmin(admin.ModelAdmin):
    list_display = ('material', 'min_stock', 'notify_email')
    autocomplete_fields = ('material',)


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'movement_type', 'adjustment_type', 'material', 'material_unit', 'quantity', 'reference', 'created_by')
    list_filter = ('movement_type', 'adjustment_type', 'created_at')
    search_fields = ('reference', 'notes')
    readonly_fields = ('created_at',)


class PrintJobItemInline(admin.TabularInline):
    model = PrintJobItem
    extra = 0
    autocomplete_fields = ('material_unit',)


@admin.register(PrintJob)
class PrintJobAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'print_name', 'machine', 'created_by')
    list_filter = ('machine', 'created_at')
    search_fields = ('print_name', 'machine')
    inlines = [PrintJobItemInline]
    readonly_fields = ('created_at',)
from django.contrib import admin

from .models import AlertThreshold, Material, MaterialType, PrintJob, StockMovement


@admin.register(MaterialType)
class MaterialTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'unit')


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ('name', 'brand', 'color', 'material_type', 'current_stock', 'business_line')
    list_filter = ('material_type', 'business_line', 'brand')
    search_fields = ('name', 'brand', 'color')


@admin.register(AlertThreshold)
class AlertThresholdAdmin(admin.ModelAdmin):
    list_display = ('material', 'min_stock', 'notify_email')
    autocomplete_fields = ('material',)


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'movement_type', 'adjustment_type', 'material', 'quantity', 'reference', 'created_by')
    list_filter = ('movement_type', 'adjustment_type', 'created_at')
    search_fields = ('reference', 'notes')
    readonly_fields = ('created_at',)


@admin.register(PrintJob)
class PrintJobAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'print_name', 'machine', 'material', 'quantity_used', 'created_by')
    list_filter = ('machine', 'created_at')
    search_fields = ('print_name', 'machine')
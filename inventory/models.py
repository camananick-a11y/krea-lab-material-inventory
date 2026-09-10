from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum


class MaterialType(models.Model):
    class Meta:
        verbose_name = 'Tipo de material'
        verbose_name_plural = 'Tipos de material'
        ordering = ['name']

    name = models.CharField('Nombre', max_length=50, unique=True)
    unit = models.CharField(
        'Unidad',
        max_length=10,
        choices=[
            ('kg', 'Kilogramos'),
            ('g', 'Gramos'),
            ('ml', 'Mililitros'),
            ('L', 'Litros'),
        ],
        default='g',
    )

    def __str__(self):
        return f"{self.name} ({self.unit})"


class Material(models.Model):
    class BusinessLine(models.TextChoices):
        ICON = 'ICON', 'ICON'
        PRINT = 'PRINT', 'PRINT'
        TECH = 'TECH', 'TECH'
        EDU = 'EDU', 'EDU'
        GENERAL = 'GENERAL', 'General'

    name = models.CharField('Nombre', max_length=50)
    material_type = models.ForeignKey(
        MaterialType, on_delete=models.PROTECT, verbose_name='Tipo de material'
    )
    brand = models.CharField('Marca', max_length=50)
    color = models.CharField('Color', max_length=50, blank=True)
    business_line = models.CharField(
        'Línea de negocio',
        max_length=20,
        choices=BusinessLine.choices,
        default=BusinessLine.GENERAL,
    )
    current_stock = models.DecimalField(
        'Stock actual', max_digits=10, decimal_places=3, default=0
    )
    unit_cost = models.DecimalField(
        'Costo unitario', max_digits=10, decimal_places=2, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Material'
        verbose_name_plural = 'Materiales'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'brand', 'color'],
                name='unique_material_brand_color',
            )
        ]

    @property
    def is_below_threshold(self):
        threshold = AlertThreshold.objects.filter(material=self).first()
        if not threshold:
            return False
        return self.current_stock < threshold.min_stock

    def __str__(self):
        return f"{self.brand} {self.name} {self.color}".strip()


class AlertThreshold(models.Model):
    class Meta:
        verbose_name = 'Umbral de alerta'
        verbose_name_plural = 'Umbrales de alerta'

    material = models.OneToOneField(
        Material, on_delete=models.CASCADE, related_name='threshold',
        verbose_name='Material',
    )
    min_stock = models.DecimalField(
        'Stock mínimo', max_digits=10, decimal_places=3
    )
    notify_email = models.BooleanField('Notificar por email', default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Alerta {self.material} < {self.min_stock}"


class StockMovement(models.Model):
    class Meta:
        verbose_name = 'Movimiento de stock'
        verbose_name_plural = 'Movimientos de stock'
        ordering = ['-created_at']

    class MovementType(models.TextChoices):
        IN = 'IN', 'Entrada'
        OUT = 'OUT', 'Salida'

    class AdjustmentType(models.TextChoices):
        PURCHASE = 'purchase', 'Compra'
        PRINT_JOB = 'print_job', 'Trabajo de impresión'
        MANUAL_IN = 'manual_in', 'Ajuste manual (entrada)'
        MANUAL_OUT = 'manual_out', 'Ajuste manual (salida)'
        WASTE = 'waste', 'Merma/desperdicio'

    material = models.ForeignKey(
        Material, on_delete=models.PROTECT, related_name='movements',
        verbose_name='Material',
    )
    movement_type = models.CharField(
        'Tipo de movimiento', max_length=3, choices=MovementType.choices
    )
    adjustment_type = models.CharField(
        'Motivo', max_length=20, choices=AdjustmentType.choices,
        default=AdjustmentType.MANUAL_IN,
    )
    quantity = models.DecimalField(
        'Cantidad', max_digits=10, decimal_places=3,
        validators=[MinValueValidator(float(0))],
    )
    reference = models.CharField(
        'Referencia', max_length=100, blank=True,
        help_text='Ej: Compra #INV-001, Trabajo #001',
    )
    notes = models.TextField('Notas', blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        null=True, blank=True, verbose_name='Registrado por',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def apply_stock_change(self):
        material = self.material
        if self.movement_type == self.MovementType.IN:
            material.current_stock += self.quantity
        else:
            material.current_stock -= self.quantity
        material.save(update_fields=['current_stock', 'updated_at'])

    def save(self, *args, **kwargs):
        if self.movement_type == self.MovementType.OUT and 'quantity' in self.__dict__:
            from django.core.exceptions import ValidationError
            if self.pk is None and self.material.current_stock < self.quantity:
                raise ValidationError(
                    f'Stock insuficiente: hay {self.material.current_stock}, '
                    f'se intenta descontar {self.quantity}.'
                )
        super().save(*args, **kwargs)
        self.apply_stock_change()

    def __str__(self):
        return f"[{self.get_movement_type_display()}] {self.material}: {self.quantity}"


class PrintJob(models.Model):
    class Meta:
        verbose_name = 'Trabajo de impresión'
        verbose_name_plural = 'Trabajos de impresión'
        ordering = ['-created_at']

    material = models.ForeignKey(
        Material, on_delete=models.PROTECT, related_name='print_jobs',
        verbose_name='Material',
    )
    quantity_used = models.DecimalField(
        'Cantidad consumida', max_digits=10, decimal_places=3
    )
    machine = models.CharField('Máquina', max_length=100)
    print_name = models.CharField('Nombre de la pieza', max_length=150, blank=True)
    laminator_data = models.JSONField(
        'Datos del laminador', null=True, blank=True,
        help_text='Datos crudos del laminador (Bambu Studio / Chitubox)',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        null=True, blank=True, verbose_name='Registrado por',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            StockMovement.objects.create(
                material=self.material,
                movement_type=StockMovement.MovementType.OUT,
                adjustment_type=StockMovement.AdjustmentType.PRINT_JOB,
                quantity=self.quantity_used,
                reference=f'Trabajo #{self.pk} - {self.print_name}',
                created_by=self.created_by,
            )

    def __str__(self):
        return f"{self.print_name} @ {self.machine} - {self.quantity_used}g"
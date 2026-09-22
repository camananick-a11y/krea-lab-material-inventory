from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class Sede(models.Model):
    class Meta:
        verbose_name = 'Sede'
        verbose_name_plural = 'Sedes'
        ordering = ['name']

    name = models.CharField('Nombre', max_length=100, unique=True)
    address = models.CharField('Dirección', max_length=200, blank=True)
    city = models.CharField('Ciudad', max_length=50, blank=True)
    is_active = models.BooleanField('Activa', default=True)

    def __str__(self):
        return self.name


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

    def recalc_stock(self):
        """Recomputa current_stock como la suma del restante de sus unidades."""
        total = Decimal('0')
        for unit in self.units.all():
            total += unit.remaining
        self.current_stock = total
        self.save(update_fields=['current_stock', 'updated_at'])

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


class MaterialUnit(models.Model):
    class Status(models.TextChoices):
        NEW = 'nueva', 'Nueva'
        IN_USE = 'en_uso', 'En uso'
        EXHAUSTED = 'agotada', 'Agotada'

    class Meta:
        verbose_name = 'Unidad de material'
        verbose_name_plural = 'Unidades de material (bobinas/botellas)'
        ordering = ['code']

    code = models.CharField(
        'Código / etiqueta QR', max_length=20, unique=True,
        help_text='Ej: FIL-001, RES-001. Coincide con la etiqueta física.',
    )
    material = models.ForeignKey(
        Material, on_delete=models.PROTECT, related_name='units',
        verbose_name='Material',
    )
    sede = models.ForeignKey(
        Sede, on_delete=models.PROTECT, related_name='units',
        null=True, blank=True, verbose_name='Sede',
    )
    finish = models.CharField('Acabado', max_length=30, blank=True)
    color = models.CharField('Color', max_length=50, blank=True)
    hex_color = models.CharField(
        'Color hexadecimal', max_length=7, blank=True,
        help_text='Ej: #1A1A1A (referencia).',
    )
    photo_ref = models.CharField(
        'Referencia de foto', max_length=200, blank=True,
        help_text='Ej: fotos/FIL-001.jpg',
    )
    gross_weight = models.DecimalField(
        'Peso bruto (g)', max_digits=10, decimal_places=3, default=0,
        help_text='Peso actual de la bobina/botella en balanza.',
    )
    empty_weight = models.DecimalField(
        'Tara: envase vacío (g)', max_digits=10, decimal_places=3, default=0,
    )
    density = models.DecimalField(
        'Densidad (g/ml)', max_digits=5, decimal_places=3,
        default=Decimal('1.10'),
        help_text='Solo resina. Típico 1.05–1.15.',
    )
    nominal_capacity = models.DecimalField(
        'Capacidad nominal', max_digits=10, decimal_places=3,
        default=Decimal('1000'),
        help_text='Capacidad de la bobina/botella en la unidad del material.',
    )
    status = models.CharField(
        'Estado', max_length=20, choices=Status.choices, default=Status.NEW,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_resin(self):
        return self.material.material_type.unit == 'ml'

    @property
    def remaining_weight(self):
        return max(self.gross_weight - self.empty_weight, Decimal('0'))

    @property
    def remaining(self):
        if self.is_resin and self.density:
            return self.remaining_weight / self.density
        return self.remaining_weight

    @property
    def percent(self):
        if self.nominal_capacity <= 0:
            return Decimal('0')
        pct = (self.remaining / self.nominal_capacity) * Decimal('100')
        return min(max(pct, Decimal('0')), Decimal('100'))

    @property
    def fill_level(self):
        pct = self.percent
        if pct >= Decimal('75'):
            return 'Lleno'
        if pct >= Decimal('50'):
            return 'Mitad'
        if pct >= Decimal('25'):
            return 'Cuarto'
        return 'Por agotar'

    @property
    def qr_url(self):
        return f"/api/inventory/u/{self.code}/"

    def adjust_content(self, quantity_in_unit):
        """Ajusta el peso bruto según la cantidad en la unidad del material.

        quantity_in_unit positivo = consumo (OUT); negativo = entrada (IN).
        Para resina la cantidad es ml y se convierte con la densidad.
        """
        grams = quantity_in_unit * self.density if self.is_resin else quantity_in_unit
        self.gross_weight = max(self.gross_weight - grams, Decimal('0'))
        self.save()

    def save(self, *args, **kwargs):
        if self.gross_weight <= self.empty_weight:
            self.status = self.Status.EXHAUSTED
        elif self.status == self.Status.EXHAUSTED:
            self.status = self.Status.IN_USE
        super().save(*args, **kwargs)
        self.material.recalc_stock()

    def __str__(self):
        return f"{self.code} · {self.material}"


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
    material_unit = models.ForeignKey(
        MaterialUnit, on_delete=models.PROTECT, null=True, blank=True,
        related_name='movements', verbose_name='Unidad (bobina/botella)',
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
        validators=[MinValueValidator(Decimal('0'))],
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
        if self.material_unit_id:
            unit_quantity = self.quantity if self.movement_type == self.MovementType.OUT else -self.quantity
            self.material_unit.adjust_content(unit_quantity)
            return
        material = self.material
        if self.movement_type == self.MovementType.IN:
            material.current_stock += self.quantity
        else:
            material.current_stock -= self.quantity
        material.save(update_fields=['current_stock', 'updated_at'])

    def save(self, *args, **kwargs):
        if self.material_unit_id:
            self.material = self.material_unit.material
        if self.pk is None and self.movement_type == self.MovementType.OUT:
            if self.material_unit_id:
                if self.material_unit.remaining < self.quantity:
                    raise ValidationError(
                        f'Stock insuficiente en {self.material_unit.code}: '
                        f'hay {self.material_unit.remaining}, '
                        f'se intenta descontar {self.quantity}.'
                    )
            elif self.material and self.material.current_stock < self.quantity:
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

    machine = models.CharField('Máquina', max_length=100)
    print_name = models.CharField('Nombre de la pieza', max_length=150, blank=True)
    laminator_data = models.JSONField(
        'Datos del laminador', null=True, blank=True,
        help_text='Datos crudos del laminador (Bambu Studio / Chitubox)',
    )
    material = models.ForeignKey(
        Material, on_delete=models.PROTECT, related_name='print_jobs',
        null=True, blank=True,
        verbose_name='Material (legado)',
        help_text='Campo de compatibilidad; usar items del trabajo.',
    )
    quantity_used = models.DecimalField(
        'Cantidad consumida (legado)',
        max_digits=10, decimal_places=3, null=True, blank=True,
        help_text='Campo de compatibilidad; el consumo real va en items.',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        null=True, blank=True, verbose_name='Registrado por',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def register_consumption(self):
        """Crea los movimientos OUT de cada item del trabajo (cambio de rollo soportado)."""
        for item in self.items.all():
            exists = StockMovement.objects.filter(
                material_unit=item.material_unit,
                movement_type=StockMovement.MovementType.OUT,
                adjustment_type=StockMovement.AdjustmentType.PRINT_JOB,
                quantity=item.quantity_used,
                reference=f'Trabajo #{self.pk} - {self.print_name}',
            ).exists()
            if not exists:
                StockMovement.objects.create(
                    material_unit=item.material_unit,
                    movement_type=StockMovement.MovementType.OUT,
                    adjustment_type=StockMovement.AdjustmentType.PRINT_JOB,
                    quantity=item.quantity_used,
                    reference=f'Trabajo #{self.pk} - {self.print_name}',
                    created_by=self.created_by,
                )

    def __str__(self):
        return f"{self.print_name} @ {self.machine}"


class PrintJobItem(models.Model):
    class Meta:
        verbose_name = 'Ítem de trabajo'
        verbose_name_plural = 'Ítems de trabajo'
        ordering = ['id']

    print_job = models.ForeignKey(
        PrintJob, on_delete=models.CASCADE, related_name='items',
        verbose_name='Trabajo',
    )
    material_unit = models.ForeignKey(
        MaterialUnit, on_delete=models.PROTECT, related_name='print_items',
        verbose_name='Unidad consumida',
        help_text='Cada ítem registra una bobina/botella usada en el trabajo (cambio de rollo).',
    )
    quantity_used = models.DecimalField(
        'Cantidad consumida', max_digits=10, decimal_places=3,
        validators=[MinValueValidator(Decimal('0'))],
    )

    def __str__(self):
        return f"{self.material_unit.code}: {self.quantity_used}"
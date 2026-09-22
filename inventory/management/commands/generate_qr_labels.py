import base64
import io
from pathlib import Path

import qrcode
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.utils import timezone
from urllib.parse import urljoin

from inventory.models import MaterialUnit


class Command(BaseCommand):
    help = (
        'Genera una hoja HTML imprimible (A4) con las etiquetas QR de las unidades. '
        'Ej: python manage.py generate_qr_labels --base-url https://inventario.krea.lab '
        '--output qr_labels.html'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--base-url', default='http://127.0.0.1:8000',
            help='Dominio público al que apuntarán los QR (sin barra final). '
                 'Ej: https://inventario.krea.lab (Fase 2 = AWS)',
        )
        parser.add_argument(
            '--output', default='qr_labels.html',
            help='Archivo HTML de salida (por defecto qr_labels.html en el directorio actual).',
        )
        parser.add_argument(
            '--material', type=int, default=None,
            help='Filtrar por id de material.',
        )
        parser.add_argument(
            '--sede', type=int, default=None,
            help='Filtrar por id de sede.',
        )
        parser.add_argument(
            '--status', default=None,
            help='Filtrar por estado (nueva|en_uso|agotada).',
        )

    def build_label(self, unit, base_url):
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=1,
        )
        target = urljoin(f'{base_url}/', unit.qr_url)
        qr.add_data(target)
        qr.make(fit=True)
        img = qr.make_image(fill_color='#1a1a1a', back_color='white')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        qr_b64 = base64.b64encode(buf.getvalue()).decode('ascii')
        return {
            'code': unit.code,
            'material': str(unit.material),
            'type_name': unit.material.material_type.name,
            'unit': unit.material.material_type.unit,
            'finish': unit.finish or '—',
            'color': unit.color,
            'sede': unit.sede.name if unit.sede else '—',
            'status': unit.get_status_display(),
            'fill_level': unit.fill_level,
            'percent': min(float(unit.percent), 100.0),
            'qr_b64': qr_b64,
        }

    def handle(self, *args, **options):
        base_url = options['base_url'].rstrip('/')
        qs = MaterialUnit.objects.select_related(
            'material', 'material__material_type', 'sede',
        ).order_by('code')
        if options['material']:
            qs = qs.filter(material_id=options['material'])
        if options['sede']:
            qs = qs.filter(sede_id=options['sede'])
        if options['status']:
            qs = qs.filter(status=options['status'])

        units = list(qs)
        if not units:
            self.stdout.write(self.style.ERROR('No hay unidades que cumplan los filtros.'))
            return

        labels = [self.build_label(u, base_url) for u in units]
        html = render_to_string('inventory/qr_labels.html', {
            'base_url': base_url,
            'generated_at': timezone.now().strftime('%d/%m/%Y %H:%M'),
            'labels': labels,
        })

        out = Path(options['output'])
        out.write_text(html, encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(
            f'Hoja generada: {out.resolve()} ({len(labels)} etiquetas, base {base_url})'
        ))
        self.stdout.write('Imprimir: abrir el HTML en un navegador y Ctrl+P '
                          '(tamaño A4, márgenes predeterminados).')
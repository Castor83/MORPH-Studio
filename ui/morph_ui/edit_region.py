"""Validate a version-bound mask for the existing image editors' final composite."""
import hashlib
import io
import os
import warnings

from PIL import Image, ImageChops

from .paths import UiError


LIMIT = 64 * 1024**2
WORKFLOWS = {'kontext': ('4', '14'), 'krea2': ('72', '29')}


def _read(files, media_id):
    info = files.info(media_id)
    if info['kind'] != 'image' or info['category'] != 'input':
        raise UiError('edit_region_image', 'Bereich und Ausgangsbild benötigen hochgeladene Bildeingaben.')
    try:
        with files.resolve(media_id).open('rb') as source:
            before = os.fstat(source.fileno())
            if not 0 < before.st_size <= LIMIT:
                raise ValueError('Image size')
            data = source.read(LIMIT + 1)
            after = os.fstat(source.fileno())
        identity = lambda stat: (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)
        if len(data) != before.st_size or identity(before) != identity(after):
            raise ValueError('Image changed')
        return data
    except (OSError, ValueError) as error:
        raise UiError('edit_region_image', 'Das Bereichsbild ist nicht vollständig lesbar (höchstens 64 MiB).') from error


def _decode(data):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            image = Image.open(io.BytesIO(data))
            if (image.format not in {'PNG', 'JPEG', 'WEBP'} or image.width * image.height > 64_000_000
                    or getattr(image, 'n_frames', 1) != 1):
                raise ValueError('Unsupported image')
            image.load()
            return image
    except (OSError, ValueError, Image.DecompressionBombWarning, Image.DecompressionBombError) as error:
        raise UiError('edit_region_image', 'Der Bereich benötigt ein einzelnes gültiges Bild mit höchstens 64 Millionen Bildpunkten.') from error


def validate_region(files, workflow_id, controls, images, project_id, parent_version_id, request):
    if workflow_id not in WORKFLOWS:
        raise UiError('edit_region_workflow', 'Bereiche sind für „Bild bearbeiten“ und „Bild mit KREA 2 bearbeiten“ verfügbar.')
    if not project_id or not parent_version_id:
        raise UiError('edit_region_context', 'Bitte zuerst einen Zwischenstand des Bildprojekts als Ausgangsbild wählen.')
    fields = {'mask_media_id', 'source_media_id', 'parent_version_id'}
    if not isinstance(request, dict) or set(request) != fields or not all(isinstance(request[key], str) for key in fields):
        raise UiError('edit_region', 'Der Bereich benötigt eine Maske und ihren zugehörigen Bild-Zwischenstand.')
    if (not isinstance(images, dict) or request['source_media_id'] != images.get('image')
            or request['parent_version_id'] != parent_version_id):
        raise UiError('edit_region_context', 'Der gemalte Bereich gehört zu einem anderen Ausgangsbild. Bitte den Bereich neu zeichnen.')
    source_data = _read(files, request['source_media_id'])
    mask_data = _read(files, request['mask_media_id'])
    with _decode(source_data) as source, _decode(mask_data) as mask:
        if source.getexif().get(274, 1) != 1:
            raise UiError('edit_region_orientation', 'Für Bereiche das gedrehte Ausgangsbild zuerst ohne EXIF-Drehung als PNG speichern und erneut wählen.')
        if source.convert('RGBA').getchannel('A').getextrema() != (255, 255):
            raise UiError('edit_region_transparency', 'Die Bereichskomposition benötigt ein deckendes Ausgangsbild. Bitte zuerst eine Kopie mit gewünschtem Hintergrund ohne Transparenz speichern und erneut wählen; Vollbildbearbeitung bleibt möglich.')
        if mask.format != 'PNG' or mask.mode not in {'L', 'RGB', 'RGBA'} or mask.getexif().get(274, 1) != 1:
            raise UiError('edit_region_mask', 'Der Bereich benötigt eine deckende Schwarz-Weiß- oder Graustufenmaske als PNG.')
        if mask.size != source.size:
            raise UiError('edit_region_size', 'Die Bereichsmaske muss genau die Pixelmaße des Ausgangsbildes haben.')
        if mask.convert('RGBA').getchannel('A').getextrema() != (255, 255):
            raise UiError('edit_region_mask', 'Die Bereichsmaske muss deckend sein; Schwarz schützt und Weiß übernimmt das Ergebnis.')
        if mask.mode in {'RGB', 'RGBA'}:
            red, green, blue = mask.convert('RGB').split()
            if ImageChops.difference(red, green).getbbox() or ImageChops.difference(red, blue).getbbox():
                raise UiError('edit_region_mask', 'Die Bereichsmaske darf nur gleiche Rot-, Grün- und Blauwerte enthalten.')
        gray = mask.convert('L')
        bounds = gray.getbbox()
        if bounds is None:
            raise UiError('edit_region_empty', 'Bitte zuerst einen Bereich ins Ausgangsbild malen.')
        width, height = source.size
        if controls['width'] * height != controls['height'] * width:
            raise UiError('edit_region_geometry', 'Für Bereiche müssen Breite und Höhe dasselbe Seitenverhältnis wie das Ausgangsbild haben. Bitte passende Maße übernehmen oder den Bereich ausschalten.',
                          {'source_width': width, 'source_height': height})
    return dict(request, mode='masked_composite', width=width, height=height, mask_bounds=list(bounds),
                source_sha256=hashlib.sha256(source_data).hexdigest(), mask_sha256=hashlib.sha256(mask_data).hexdigest())


def verify_region(files, region):
    """Fence changes made while the service and its node schemas were checked."""
    for role in ['source', 'mask']:
        if hashlib.sha256(_read(files, region[role + '_media_id'])).hexdigest() != region[role + '_sha256']:
            raise UiError('edit_region_changed', 'Ausgangsbild oder Bereichsmaske wurde geändert. Bitte den Zwischenstand erneut wählen und den Bereich neu zeichnen.')


def composite_graph(graph, workflow_id, mask_name):
    if workflow_id not in WORKFLOWS:
        raise UiError('edit_region_workflow', 'Dieses Werkzeug unterstützt keine Bereichskomposition.')
    image_node, save_node = WORKFLOWS[workflow_id]
    mask_node, composite_node = '90001', '90002'
    if mask_node in graph or composite_node in graph:
        raise UiError('edit_region_graph', 'Die Workflow-Vorlage belegt bereits die benötigten Bereichsknoten.')
    generated = graph[save_node]['inputs']['images']
    graph[mask_node] = {'class_type': 'LoadImageMask', 'inputs': {'image': mask_name, 'channel': 'red'}}
    graph[composite_node] = {'class_type': 'ImageCompositeMasked', 'inputs': {
        'destination': [image_node, 0], 'source': generated, 'x': 0, 'y': 0,
        'resize_source': True, 'mask': [mask_node, 0]}}
    graph[save_node]['inputs']['images'] = [composite_node, 0]
    return graph

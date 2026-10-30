"""Public resource measurements; never infer loaded models from job history."""
from datetime import datetime, timezone
import math

SOURCE = 'ComfyUI /system_stats'


def memory(total, free):
    def number(value):
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            return None
        return value
    total, free = number(total), number(free)
    if total is not None and free is not None and free > total:
        free = None
    return {'total':total, 'free':free, 'used':total - free if total is not None and free is not None else None}


def snapshot(stats=None):
    result = {'available':False, 'measured_at':None, 'source':SOURCE, 'devices':[],
              'ram':memory(None, None), 'model_state':'unknown',
              'unload':{'allowed':False, 'reason':'Der Rechendienst ist nicht zuverlässig erreichbar.'}}
    if not (isinstance(stats, dict) and isinstance(stats.get('system'), dict)
            and isinstance(stats.get('devices'), list)):
        result['error'] = 'Ressourcenwerte momentan nicht verfügbar.'
        return result
    result.update(available=True, measured_at=datetime.now(timezone.utc).isoformat())
    result['ram'] = memory(stats['system'].get('ram_total'), stats['system'].get('ram_free'))
    for item in stats['devices']:
        if not isinstance(item, dict):
            continue
        values = memory(item.get('vram_total'), item.get('vram_free'))
        result['devices'].append({
            'name':item['name'][:200] if isinstance(item.get('name'), str) else None,
            'type':item['type'][:30] if isinstance(item.get('type'), str) else None,
            'index':item['index'] if type(item.get('index')) is int and item['index'] >= 0 else None,
            'vram_total':values['total'], 'vram_free':values['free'], 'vram_used':values['used']})
    return result

"""Decode the three actual MCP video outputs and record their metadata."""
import json
import re
import subprocess
from pathlib import Path

report = Path('D:/MORPH-Studio/reports/wan-lmstudio')
ffmpeg = Path('D:/MORPH-Studio/ComfyUI_windows_portable/python_embeded/Lib/site-packages/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe')
outputs = json.loads((report / 'first-video-outputs-mcp.json').read_text(encoding='utf-8-sig'))
print(json.dumps(outputs, ensure_ascii=False))
videos = []
for entry in outputs.get('outputs', []):
    path = Path(entry['path'])
    if path.suffix.lower() != '.mp4':
        continue
    assert path.is_file(), path
    result = subprocess.run([str(ffmpeg), '-hide_banner', '-nostats', '-i', str(path), '-map', '0:v:0', '-progress', 'pipe:1', '-f', 'null', '-'], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)
    frames = re.findall(r'^frame=(\d+)', result.stdout, re.MULTILINE)
    stream = re.search(r'Stream[^\n]*Video: h264[^\n]*?,\s*(\d+)x(\d+)[^\n]*?\b([\d.]+) fps', result.stderr)
    duration = re.search(r'Duration: ([\d:.]+)', result.stderr)
    assert result.returncode == 0 and frames and stream and duration, result.stderr
    assert int(stream[1]) > 0 and int(stream[2]) > 0, stream.group(0)
    videos.append({'path': str(path), 'bytes': path.stat().st_size, 'codec': 'h264', 'width': int(stream[1]), 'height': int(stream[2]), 'fps': float(stream[3]), 'duration': duration[1], 'decoded_frames': int(frames[-1]), 'decode_exit_code': result.returncode})
    (report / (path.stem + '-decode.log')).write_text(result.stderr + '\n' + result.stdout, encoding='utf-8')
assert len(videos) == 3, videos
receipt = {'prompt_id': outputs['prompt_id'], 'all_three_decoded': True, 'videos': videos}
(report / 'first-video-media-check.json').write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps(receipt, ensure_ascii=False))

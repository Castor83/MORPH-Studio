"""Create three project-local NTFS hardlinks; never copy or write weights."""
import json
import os
from pathlib import Path
import stat
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from morph_ui.paths import ProjectPaths, UiError
from morph_ui.model_library import ModelLibrary

FILES = [('noctQUncensoredRealismBuiltOn_v40Base_fp16.safetensors','diffusion_models','qwen_model'), ('qwenImage21TextEncoderOriginal_v10_3241887.safetensors','text_encoders','qwen_encoder'), ('qwenImage21VAEOriginalBf16_v10.safetensors','vae','qwen_vae')]


def register(paths):
    library = ModelLibrary(paths)
    prepared = []
    for name,directory,role in FILES:
        source = Path(library.resolve('checkpoints/' + name,role)['path'])
        relative = directory + '/morph-ui-qwen21/' + name
        target = paths.models / relative
        paths.inside(paths.models,relative)
        for component in [paths.models / directory,target.parent,target]:
            if component.exists() or component.is_symlink():
                info = component.lstat()
                if component.is_symlink() or getattr(info,'st_file_attributes',0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                    raise UiError('link_path','Die Qwen-Zuordnung enthält eine unerwartete Dateiverknüpfung.',str(component))
        exists = target.exists()
        if exists and not os.path.samefile(source,target):
            raise UiError('link_conflict','Am Qwen-Ziel liegt bereits eine andere Datei. Sie bleibt erhalten.',str(target))
        prepared.append((source,target,exists))
    result = []
    for source,target,exists in prepared:
        # All source roles and destinations were checked before the first mutation.
        target.parent.mkdir(parents=True,exist_ok=True)
        if not exists:
            os.link(source,target,follow_symlinks=False)
        if not os.path.samefile(source,target):
            raise UiError('link_verify','Die Dateizuordnung konnte nicht bestätigt werden.',str(target))
        result.append({'source':str(source),'target':str(target),'created':not exists,'same_file':True,'size':source.stat().st_size})
    return result


if __name__ == '__main__':
    paths = ProjectPaths(Path(__file__).resolve().parents[1])
    result = register(paths)
    proof = paths.inside(paths.root,'reports/safetensors-ui-20261011/qwen-file-links.json')
    proof.parent.mkdir(parents=True,exist_ok=True)
    proof.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))

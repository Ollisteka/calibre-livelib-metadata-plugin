"""Validate a release tag without importing Calibre and select its assets."""
import ast
import os
from pathlib import Path
import re


def release_info(tag, root):
    match = re.fullmatch(r'(metadata|reading-dates)-v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', tag)
    if not match:
        raise ValueError('Expected metadata-vX.Y.Z or reading-dates-vX.Y.Z')
    plugin = match[1]
    source, archive, notes, class_name = {
        'metadata': ('plugin', 'LiveLib.Metadata.zip', 'RELEASE_NOTES.md', 'LiveLibMetadata'),
        'reading-dates': ('reading_plugin', 'LiveLib.ReadingDates.zip', 'RELEASE_NOTES_READING_DATES.md', 'LiveLibReadingDates'),
    }[plugin]
    tree = ast.parse((root / source / '__init__.py').read_text(encoding='utf-8'))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name)
    version = next(ast.literal_eval(node.value) for node in cls.body
                   if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'version' for t in node.targets))
    if version != tuple(map(int, match.groups()[1:])):
        raise ValueError(f'Tag {tag} does not match plugin version {version}')
    if not (root / notes).read_text(encoding='utf-8').strip():
        raise ValueError('Release notes are empty')
    return dict(plugin=plugin, archive='dist/' + archive, notes=notes)


if __name__ == '__main__':
    info = release_info(os.environ['RELEASE_TAG'], Path(__file__).resolve().parents[1])
    with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
        for key, value in info.items():
            output.write(f'{key}={value}\n')

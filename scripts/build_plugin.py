"""Build the installable ZIP without caches or development files."""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def build_plugin(root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    source = root / 'plugin'
    output = root / 'dist' / 'LiveLib.Metadata.zip'
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob('*')):
            relative = path.relative_to(source)
            if path.is_file() and '__pycache__' not in relative.parts and path.suffix != '.pyc' and path.name != '.DS_Store':
                archive.write(path, relative.as_posix())
    return output


if __name__ == '__main__':
    print(build_plugin())

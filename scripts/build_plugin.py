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


def build_reading_plugin(root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    output = root / 'dist' / 'LiveLib.ReadingDates.zip'
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        for path in sorted((root / 'reading_plugin').glob('*.py')):
            archive.write(path, path.name)
        for path in sorted((root / 'reading_plugin/images').glob('*.png')):
            archive.write(path, 'images/' + path.name)
        archive.writestr('plugin-import-name-livelib_reading_dates.txt', '')
        archive.write(root / 'plugin/providers/livelib/dates.py', 'dates.py')
    return output


if __name__ == '__main__':
    print(build_plugin())
    print(build_reading_plugin())

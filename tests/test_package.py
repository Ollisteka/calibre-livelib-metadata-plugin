import importlib.util
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('build_plugin', ROOT / 'scripts/build_plugin.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def test_archive_content_and_import(tmp_path):
    import shutil
    shutil.copytree(ROOT / 'plugin', tmp_path / 'plugin')
    nested_cache = tmp_path / 'plugin/providers/livelib/__pycache__'
    nested_cache.mkdir(exist_ok=True)
    (nested_cache / 'unwanted.pyc').write_bytes(b'cache')
    archive = builder.build_plugin(tmp_path)
    with ZipFile(archive) as zipped:
        names = set(zipped.namelist())
    expected = {str(p.relative_to(ROOT / 'plugin')).replace('\\', '/')
                for p in (ROOT / 'plugin').rglob('*.py')}
    assert names == expected
    assert '__init__.py' in names
    assert 'matching.py' in names
    # This is a Python ZIP import with Calibre stubs, not Calibre integration.
    code = '''
import importlib, sys, types, zipimport
from calibre_stubs import install
install()
archive = sys.argv[1]
package = types.ModuleType('archive_plugin')
package.__package__ = package.__name__
package.__path__ = [archive]
sys.modules[package.__name__] = package
exec(zipimport.zipimporter(archive).get_code('__init__'), package.__dict__)
assert package.LiveLibMetadata().name == 'LiveLib Metadata'
for name in sys.argv[2:]:
    importlib.import_module('archive_plugin.' + name)
'''
    modules = sorted(name[:-3].replace('/', '.') for name in names if not name.endswith('__init__.py'))
    subprocess.run([sys.executable, '-c', code, str(archive), *modules],
                   cwd=ROOT / 'tests', check=True, capture_output=True, text=True)

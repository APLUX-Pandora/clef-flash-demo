"""Package the prebuilt SDK; never compile an inference engine during installation."""
import platform
from pathlib import Path
import shutil
from setuptools import setup, Distribution
from setuptools.command.build_py import build_py
from wheel.bdist_wheel import bdist_wheel

ROOT = Path(__file__).resolve().parent

class NativeDistribution(Distribution):
    def has_ext_modules(self):
        return True

class PlatformWheel(bdist_wheel):
    def get_tag(self):
        _, _, platform_tag = super().get_tag()
        return "py3", "none", platform_tag


class BuildSDK(build_py):
    def run(self):
        library = ROOT / 'lib/libclef.so'
        if not library.is_file():
            raise RuntimeError('Missing sdk/lib/libclef.so; stage the matching prebuilt SDK before installation')
        if platform.system() != 'Linux' or platform.machine().lower() not in ('aarch64', 'arm64'):
            raise RuntimeError('This native SDK requires Linux AArch64')
        super().run()
        target = Path(self.build_lib) / 'pandora_clef_flash/lib'
        target.mkdir(parents=True, exist_ok=True)
        shutil.copy2(library, target / library.name)
        openmp = library.parent / 'libgomp.so.1'
        if not openmp.is_file():
            raise RuntimeError('Missing GNU OpenMP runtime next to sdk/lib/libclef.so')
        shutil.copy2(openmp, target / openmp.name)
        qnn_runtime = library.parent / 'qnn248'
        if not qnn_runtime.is_dir():
            raise RuntimeError('Missing QNN runtime next to sdk/lib/libclef.so')
        shutil.copytree(qnn_runtime, target / qnn_runtime.name, dirs_exist_ok=True)
        for name in ['LICENSE', 'LICENSING.md', 'NOTICE', 'LICENSES']:
            source = ROOT / 'lib' / name
            if not source.exists():
                raise RuntimeError('Missing SDK legal material: ' + name)
            if source.is_dir(): shutil.copytree(source, target / name, dirs_exist_ok=True)
            else: shutil.copy2(source, target / name)

setup(package_dir={'': 'python'}, packages=['pandora_clef_flash'],
      cmdclass={'build_py': BuildSDK, 'bdist_wheel': PlatformWheel}, distclass=NativeDistribution)

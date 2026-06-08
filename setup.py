from setuptools import setup, find_packages, Extension
from setuptools.command.build_ext import build_ext
import subprocess
import os
import sysconfig
import struct
import sys


# Override to force 64-bit
class Build_ext_win_amd64(build_ext):
    def finalize_options(self):
        super().finalize_options()
        # Force amd64 platform_name
        self.plat_name = 'win-amd64'


def update_submodules():
    if os.path.exists(".git"):
        try:
            subprocess.check_call(["git", "submodule", "update", "--init", "--recursive"])
        except subprocess.CalledProcessError as e:
            print(f"Failed to update submodules: {e}")
            raise


update_submodules()


def get_windows_link_args():
    """Dynamically determine the Python lib path and name for MSVC linking."""
    prefix = sys.prefix
    lib_dir = os.path.join(prefix, 'libs')
    ver = f"{sys.version_info.major}{sys.version_info.minor}"
    python_lib = f"python{ver}.lib"
    return [f'/LIBPATH:{lib_dir}', python_lib]


zipnn_core_extension = Extension(
    "zipnn_core",
    sources=[
        "csrc/zipnn_core_module.c",
        "csrc/zipnn_core.c",
        "csrc/data_manipulation_dtype16.c",
        "csrc/data_manipulation_dtype32.c",
        "include/FiniteStateEntropy/lib/fse_compress.c",
        "include/FiniteStateEntropy/lib/fse_decompress.c",
        "include/FiniteStateEntropy/lib/huf_compress.c",
        "include/FiniteStateEntropy/lib/huf_decompress.c",
        "include/FiniteStateEntropy/lib/entropy_common.c",
        "include/FiniteStateEntropy/lib/hist.c",
    ],
    include_dirs=["include/FiniteStateEntropy/lib/", "csrc/"],
    extra_compile_args=(
        ['/O2', '/W3'] if os.name == 'nt' else ['-O3', '-Wall', '-Wextra']
    ),
    extra_link_args=(
        get_windows_link_args() if os.name == 'nt' else ['-O3', '-Wall', '-Wextra']
    ),
)

setup(
    name="zipnn",
    version="0.5.4",
    author="ZipNN Contributors",
    description="A Lossless Compression Library for AI pipelines",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/zipnn/zipnn",
    packages=find_packages(include=["zipnn", "zipnn.*"]),
    cmdclass={'build_ext': Build_ext_win_amd64} if os.name == 'nt' else {},
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
    install_requires=[
        'numpy>=1.17.0',
        'safetensors>=0.4.0',
        "torch>=2.0.0",
    ],
    ext_modules=[zipnn_core_extension],  # Add the C extension module here
)

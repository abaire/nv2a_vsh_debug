#!/usr/bin/env python3

from build_cffi import FfiPreBuildExtension

if __name__ == "__main__":
    from setuptools import setup

    setup(
        cffi_modules=["build_cffi.py:ffibuilder"],
        cmdclass={"build_ext": FfiPreBuildExtension},
    )

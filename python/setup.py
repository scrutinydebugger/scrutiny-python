#    setup.py
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

from setuptools import setup, find_packages
import scrutiny

setup(
    name=scrutiny.__name__,
    description='Scrutiny debug framework',
    url='https://github.com/scrutinydebugger/scrutiny',
    version=scrutiny.__version__,
    author=scrutiny.__author__,
    license=scrutiny.__license__,

    packages=find_packages(),
    include_package_data=True,  # look for MANIFEST.in for each package

    setup_requires=[],
    install_requires=[
        'appdirs',
        'pyelftools',
        'websockets',
    ],
    extras_require={
        'dev': [
            'pytest',
        ]
    },

    entry_points={
        "console_scripts": [
            "scrutiny = scrutiny.__main__",
        ]
    },
)

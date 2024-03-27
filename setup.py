#    setup.py
#        Standard installation script
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

from setuptools import setup, find_packages
import scrutiny
import sys
import os

dependencies = [
    'appdirs>=1.4.4',
    'pyelftools>=0.29',
    'websockets>=11.0.3',
    'sortedcontainers>=2.4',
    'pyserial>=3.5'
]

doc_dependencies = []
if (sys.version_info.major, sys.version_info.minor) >= (3, 9):
    doc_dependencies = [
        'sphinx-book-theme==1.1.2',
        'sphinx==7.2.6'
    ]

setup(
    name=scrutiny.__name__,
    python_requires='>3.8',
    description='Scrutiny debugger Python framework',
    url='https://github.com/scrutinydebugger/scrutiny-python',
    version=scrutiny.__version__,
    author=scrutiny.__author__,
    license=scrutiny.__license__,

    packages=find_packages(where='.', exclude=["test", "test.*"], include=['scrutiny', "scrutiny.*"]),
    package_data = {
        'scrutiny': ['py.typed'],
    },

    setup_requires=[],
    install_requires=dependencies,
    extras_require={
        'test': ['mypy', 'coverage'] + doc_dependencies,
        'dev': ['mypy', 'ipdb', 'autopep8', 'coverage'] + doc_dependencies
    },
    entry_points={
        "console_scripts": [
            "scrutiny=scrutiny.__main__:main",
        ]
    },
)

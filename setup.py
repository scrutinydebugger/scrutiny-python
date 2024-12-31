#    setup.py
#        Standard installation script
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from setuptools import setup, find_packages #type:ignore
import sys
import os 

os.chdir(os.path.dirname(__file__))

import scrutiny

dependencies = [
    'appdirs==1.4.4',
    'pyelftools==0.31',
    'sortedcontainers==2.4.0',
    'pyserial==3.5',
    'pylink-square==1.3.0',
    'PySide6-QtAds==4.3.1.2',
    'PySide6==6.8.1'
]

doc_dependencies = []
if (sys.version_info.major, sys.version_info.minor) >= (3, 9):
    doc_dependencies = [
        'sphinx-book-theme==1.1.2',
        'sphinx==7.2.6'
    ]

def get_gui_assets():
    asset_dir = os.path.abspath('scrutiny/gui/assets')
    if not os.path.isfile(os.path.join(asset_dir, '__init__.py')):
        raise RuntimeError(f"GUI asset path does not exists {asset_dir}")

    def generate():
        for dirpath, _, files in os.walk(asset_dir):
            for file in files:
                if not file.endswith(('.py', '.pyc')):
                    yield os.path.join(dirpath, file)
    return list(generate())


setup(
    name=scrutiny.__name__,
    python_requires='>=3.9',
    description='Scrutiny debugger Python framework',
    url='https://github.com/scrutinydebugger/scrutiny-python',
    version=scrutiny.__version__,
    author=scrutiny.__author__,
    license=scrutiny.__license__,

    packages=find_packages(where='.', exclude=["test", "test.*"], include=['scrutiny', "scrutiny.*"]),
    package_data = {
        'scrutiny': ['py.typed'] + get_gui_assets(),
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

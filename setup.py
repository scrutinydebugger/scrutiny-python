#    setup.py
#        Standard installation script
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2021 Scrutiny Debugger

#type: ignore 

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
    'PySide6-QtAds==4.4.0',
    'PySide6==6.9.0'
]

if sys.version_info < (3,11):
    dependencies.append("typing-extensions==4.12.2")

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
    name="scrutinydebugger",    # Pypi name
    python_requires='>=3.9',
    description='Scrutiny Debugger Python framework',
    url='https://github.com/scrutinydebugger/scrutiny-main',
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
        'dev': ['mypy', 'ipdb', 'autopep8', 'coverage'] + doc_dependencies,
        'build': [
            'nuitka==2.6.9',    # 2.7.3- is broken on Linux/Mac.   
            'imageio==2.37.0', 
            'build==1.2.2',
            'pip-licenses==5.0.0'
            ] 
    },
    entry_points={
        "console_scripts": [
            f"scrutiny=scrutiny.__main__:scrutiny_cli",
            f"scrutiny_server=scrutiny.__main__:scrutiny_server",
            f"scrutiny_gui=scrutiny.__main__:scrutiny_gui_with_server",
        ]
    },
)

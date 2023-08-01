#    setup.py
#        Standard installation script
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

from setuptools import setup, find_packages
import scrutiny

dependencies = [
    'appdirs>=1.4.4',
    'pyelftools>=0.29',
    'websockets>=11.0.3',
    'sortedcontainers>=2.4',
    'pyserial>=3.5'
]

setup(
    name=scrutiny.__name__,
    python_requires='>3.8',
    description='Scrutiny debugger Python framework',
    url='https://github.com/scrutinydebugger/scrutiny-python',
    version=scrutiny.__version__,
    author=scrutiny.__author__,
    license=scrutiny.__license__,

    packages=find_packages(),
    include_package_data=True,  # look for MANIFEST.in for each package

    setup_requires=[],
    install_requires=dependencies,
    extras_require={
        'test': ['mypy', 'coverage'],
        'dev': ['mypy', 'ipdb', 'autopep8', 'coverage']
    },
    entry_points={
        "console_scripts": [
            "scrutiny=scrutiny.__main__:main",
        ]
    },
)

#    setup.py
#        Standard installation script
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

from setuptools import setup, find_packages
import scrutiny
import platform
import logging


dependencies = [
    'appdirs',
    'pyelftools',
    'websockets',
    'sortedcontainers',
]

# todo : Update this version check when cefpython3 is released for 3.10
if platform.python_version() >= "3.10.0":
    logging.warning("CEF Python 3 is not available for Python %s. Skipping installation. GUI will be rendered in a web browser" % platform.python_version())
else:
    dependencies += 'cefpython3'


setup(
    name=scrutiny.__name__,
    python_requires='>3.8',
    description='Scrutiny debug framework',
    url='https://github.com/scrutinydebugger/scrutiny-python',
    version=scrutiny.__version__,
    author=scrutiny.__author__,
    license=scrutiny.__license__,

    packages=find_packages(),
    include_package_data=True,  # look for MANIFEST.in for each package

    setup_requires=[],
    install_requires = dependencies,
    extras_require = {
        'test' : ['mypy'],
        'dev' : ['mypy', 'ipdb']
    },
    entry_points={
        "console_scripts": [
            "scrutiny=scrutiny.__main__:main",
        ]
    },
)

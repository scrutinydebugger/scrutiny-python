from setuptools import setup, find_packages

setup(
    name='scrutiny',
    description='Scrutiny debug framework',
    url='https://github.com/scrutinydebugger/scrutiny',
    version='0.0.1',
    author='Pier-Yves Lessard',
    author_email='py.lessard@gmail.com',
    license='MIT',

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

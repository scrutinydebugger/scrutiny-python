import pkg_resources  # part of setuptools
__version__ = pkg_resources.require("scrutiny")[0].version

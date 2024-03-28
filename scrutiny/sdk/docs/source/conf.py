# type: ignore
# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

from os import path
import scrutiny

module_dir=path.normpath(path.dirname(scrutiny.__file__))
scrutiny_fs_dir= path.normpath(path.join(path.dirname(__file__), '..', '..', '..'))
if module_dir != scrutiny_fs_dir:
    print(f"Loaded scrutiny module is an installed one at {module_dir}. Cannot use this module for version deduction.")
    needs_sphinx = 'BAD SCRUTINY VERSION'    # Seems like the most efficient way to trigger an error from this file.

project = 'Scrutiny Python SDK'
copyright = '2021 scrutinydebugger'
author = 'scrutinydebugger'
release = f'v{scrutiny.__version__}'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.mathjax',
    'sphinx.ext.viewcode'
]

templates_path = ['_templates']
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_book_theme"
html_static_path = ['_static']
html_css_files = [
    'css/custom.css',
]

autodoc_typehints = 'description'
autodoc_warningiserror = True

html_theme_options = {
    'show_prev_next': True,
    'show_toc_level': 1,
    'use_download_button': False,
    'use_fullscreen_button': False,
    'navigation_with_keys': False,
    "icon_links": [
        {
            "name": "GitHub",
            "url": "https://github.com/scrutinydebugger/scrutiny-python",  # required
            "icon": "fa-brands fa-square-github",
            "type": "fontawesome",
        }
    ],
    "external_links": [
        ("Github", "https://github.com/scrutinydebugger/scrutiny-python")]
}

autoclass_content = 'class'
autodoc_class_signature='separated'

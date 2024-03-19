# type : ignore
# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'Scrutiny Python SDK'
copyright = '2021 scrutinydebugger'
author = 'scrutinydebugger'
release = 'v0.1'

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

autoclass_content = 'init'

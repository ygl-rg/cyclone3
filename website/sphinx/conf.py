# Ensure we get the local copy of tornado instead of what's on the standard path
import os
import sys
sys.path.insert(0, os.path.abspath("../.."))
import cyclone

master_doc = "index"

project = "cyclone"
copyright = "2013, Alexandre Fiori"

version = release = cyclone.version

extensions = ["sphinx.ext.autodoc",
              "sphinx.ext.coverage",
              "sphinx.ext.viewcode"]

primary_domain = 'py'
default_role = 'py:obj'

autodoc_member_order = "bysource"
autoclass_content = "both"

coverage_skip_undoc_in_source = True
#coverage_ignore_modules = [
#    "tornado.platform.twisted",
#    ]
# I wish this could go in a per-module file...
#coverage_ignore_classes = [
#    # tornado.gen
#    "Multi",
#    "Runner",
#    "YieldPoint",
#
#    # tornado.ioloop
#    "PollIOLoop",
#
#    # tornado.web
#    "ChunkedTransferEncoding",
#    "GZipContentEncoding",
#    "OutputTransform",
#    "TemplateModule",
#    "url",
#
#    # tornado.websocket
#    "WebSocketProtocol",
#    "WebSocketProtocol13",
#    "WebSocketProtocol76",
#    ]
#
#coverage_ignore_functions = [
#    # various modules
#    "doctests",
#    "main",
#]

html_static_path = [os.path.abspath("../static")]
html_style = "sphinx.css"
highlight_language = "none"
html_theme_options = dict(
    footerbgcolor="#fff",
    footertextcolor="#000",
    sidebarbgcolor="#fff",
    #sidebarbtncolor
    sidebartextcolor="#4d8cbf",
    sidebarlinkcolor="#216093",
    relbarbgcolor="#fff",
    relbartextcolor="#000",
    relbarlinkcolor="#216093",
    bgcolor="#fff",
    textcolor="#000",
    linkcolor="#216093",
    visitedlinkcolor="#216093",
    headbgcolor="#fff",
    headtextcolor="#4d8cbf",
    codebgcolor="#fff",
    codetextcolor="#060",
    bodyfont="Georgia, serif",
    headfont="Calibri, sans-serif",
    stickysidebar=True,
    )

latex_documents = [
    ('index', 'cyclone.tex', 'cyclone documentation', 'Alexandre Fiori',
     'manual', False),
    ]

"""Performance-only projections; no uncontrolled HAR strings are retained."""

from .core import HarError, load_har, project_har
from .render import render_html

__all__ = ["HarError", "load_har", "project_har", "render_html"]
__version__ = "0.1.0"

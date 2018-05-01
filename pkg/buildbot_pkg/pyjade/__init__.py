from __future__ import absolute_import
from .parser import Parser
from .compiler import Compiler
from .utils import process
from .filters import register_filter
from .ext import html

simple_convert = lambda t: html.process_jade(t)

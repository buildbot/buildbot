
from __future__ import absolute_import
from __future__ import print_function

import sys
import textwrap
from pkg_resources import parse_version

# Monkey-patch Sphinx to treat unhiglighted code as error.
import sphinx
import sphinx.highlighting
from sphinx.errors import SphinxWarning

# Versions of Sphinx below changeset 1860:19b394207746 (before v0.6.6 release)
# won't work due to different PygmentsBridge interface.
required_sphinx_version = '0.6.6'
sphinx_version_supported = \
    parse_version(sphinx.__version__) >= parse_version(required_sphinx_version)

# This simple monkey-patch allows either fail on first unhighlighted block or
# print all unhighlighted blocks and don't fail at all.
# First behaviour is useful for testing that all code is highlighted, second ---
# for fixing lots of unhighlighted code.
fail_on_first_unhighlighted = True


class UnhighlightedError(SphinxWarning):
    pass

# PygmentsBridge.unhighlighted() added in Sphinx in changeset 574:f1c885fdd6ad
# (0.5 release).


def patched_unhighlighted(self, source):
    indented_source = '    ' + '\n    '.join(source.split('\n'))

    if fail_on_first_unhighlighted:
        msg = textwrap.dedent(u"""\
            Block not highlighted:

            %s

            If it should be unhighlighted, please specify explicitly language of
            this block as "none":

            .. code-block:: none

                ...

            If this block is Python example, then it probably contains syntax
            errors, such as unmatched brackets or invalid indentation.

            Note that in most places you can use "..." in Python code as valid
            anonymous expression.
            """) % indented_source
        raise UnhighlightedError(msg)
    else:
        msg = textwrap.dedent(u"""\
            Unhighlighted block:

            %s

            """) % indented_source
        sys.stderr.write(msg.encode('ascii', 'ignore'))

        return orig_unhiglighted(self, source)

# Compatible with PygmentsBridge.highlight_block since Sphinx'
# 1860:19b394207746 changeset (v0.6.6 release)


def patched_highlight_block(self, *args, **kwargs):
    try:
        return orig_highlight_block(self, *args, **kwargs)
    except UnhighlightedError as ex:
        msg = ex.args[0]
        if 'warn' in kwargs:
            kwargs['warn'](msg)

        raise


def setup(app):
    global orig_unhiglighted, orig_highlight_block
    if sphinx_version_supported:
        orig_unhiglighted = sphinx.highlighting.PygmentsBridge.unhighlighted
        orig_highlight_block = sphinx.highlighting.PygmentsBridge.highlight_block

        sphinx.highlighting.PygmentsBridge.unhighlighted = patched_unhighlighted
        sphinx.highlighting.PygmentsBridge.highlight_block = patched_highlight_block
    else:
        msg = textwrap.dedent("""\
            WARNING: Your Sphinx version %s is too old and will not work with
            monkey-patch for checking unhighlighted code.  Minimal required version
            of Sphinx is %s.  Check disabled.
            """) % (sphinx.__version__, required_sphinx_version)
        sys.stderr.write(msg)

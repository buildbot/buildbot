# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

from __future__ import absolute_import
from __future__ import print_function

try:
    from twisted.logger import Logger
except ImportError:
    from twisted.python import log

    class Logger(object):
        """A simplistic backporting of the new logger system for old versions of twisted"""
        def _log(self, format, *args, **kwargs):
            log.msg(format.format(args, **kwargs))

        # legacy logging system do not support log level.
        # We don't bother inventing something. If needed, user can upgrade
        debug = _log
        info = _log
        warn = _log
        error = _log
        critical = _log

        def failure(self, format, failure, *args, **kwargs):
            formatted = format.format(args, **kwargs)
            try:
                log.error(failure, formatted)
            except AttributeError:
                self.error(failure, formatted)

__all__ = ["Logger"]

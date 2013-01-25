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
import logging
from twisted.python import log

# this class bridges Python's `logging` module into Twisted's log system.
# SqlAlchemy query logging uses `logging`, so this provides a way to enter
# queries into the Twisted log file.

class PythonToTwistedHandler(logging.Handler):

    def emit(self, record):
        log.msg(record.getMessage())

def log_from_engine(engine):
    # add the handler *before* enabling logging, so that no "default" logger
    # is added automatically, but only do so once.  This is important since
    # logging's loggers are singletons
    if not engine.logger.handlers:
        engine.logger.addHandler(PythonToTwistedHandler())
    engine.echo = True

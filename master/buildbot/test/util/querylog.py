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
import contextlib

from twisted.python import log

# this class bridges Python's `logging` module into Twisted's log system.
# SqlAlchemy query logging uses `logging`, so this provides a way to enter
# queries into the Twisted log file.


class PythonToTwistedHandler(logging.Handler):

    def emit(self, record):
        log.msg(record.getMessage())


_handler = None


def start_log_queries():
    global _handler
    if _handler is None:
        _handler = PythonToTwistedHandler()

    # In 'sqlalchemy.engine' logging namespace SQLAlchemy outputs SQL queries
    # on INFO level, and SQL queries results on DEBUG level.
    logger = logging.getLogger('sqlalchemy.engine')

    # TODO: this is not documented field of logger, so it's probably private.
    prev_level = logger.level
    logger.setLevel(logging.INFO)

    logger.addHandler(_handler)

    # Do not propagate SQL echoing into ancestor handlers
    prev_propagate = logger.propagate
    logger.propagate = False

    # Return previous values of settings, so they can be carefully restored
    # later.
    return prev_level, prev_propagate


def stop_log_queries(level=None, propagate=None):
    assert _handler is not None

    logger = logging.getLogger('sqlalchemy.engine')
    logger.removeHandler(_handler)

    # Restore logger settings or set them to reasonable defaults.
    if propagate is not None:
        logger.propagate = propagate
    else:
        logger.propagate = True

    if level is not None:
        logger.setLevel(level)
    else:
        logger.setLevel(logging.NOTSET)


@contextlib.contextmanager
def log_queries():
    level, propagate = start_log_queries()
    yield
    stop_log_queries(level=level, propagate=propagate)

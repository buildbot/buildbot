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
from __future__ import division
from __future__ import print_function

import contextlib
import logging

from twisted.python import log

# These routines provides a way to dump SQLAlchemy SQL commands and their
# results into Twisted's log.
# Logging wrappers are not re-entrant.


class _QueryToTwistedHandler(logging.Handler):

    def __init__(self, log_query_result=False, record_mode=False):
        logging.Handler.__init__(self)

        self._log_query_result = log_query_result
        self.recordMode = record_mode
        self.records = []

    def emit(self, record):
        if self.recordMode:
            self.records.append(record.getMessage())
            return
        if record.levelno == logging.DEBUG:
            if self._log_query_result:
                log.msg("{name}:{thread}:result: {msg}".format(
                    name=record.name,
                    thread=record.threadName,
                    msg=record.getMessage()))
        else:
            log.msg("{name}:{thread}:query:  {msg}".format(
                name=record.name,
                thread=record.threadName,
                msg=record.getMessage()))


def start_log_queries(log_query_result=False, record_mode=False):
    handler = _QueryToTwistedHandler(
        log_query_result=log_query_result, record_mode=record_mode)

    # In 'sqlalchemy.engine' logging namespace SQLAlchemy outputs SQL queries
    # on INFO level, and SQL queries results on DEBUG level.
    logger = logging.getLogger('sqlalchemy.engine')

    # TODO: this is not documented field of logger, so it's probably private.
    handler.prev_level = logger.level
    logger.setLevel(logging.DEBUG)

    logger.addHandler(handler)

    # Do not propagate SQL echoing into ancestor handlers
    handler.prev_propagate = logger.propagate
    logger.propagate = False

    # Return previous values of settings, so they can be carefully restored
    # later.
    return handler


def stop_log_queries(handler):
    assert isinstance(handler, _QueryToTwistedHandler)
    logger = logging.getLogger('sqlalchemy.engine')
    logger.removeHandler(handler)

    # Restore logger settings or set them to reasonable defaults.
    logger.propagate = handler.prev_propagate

    logger.setLevel(handler.prev_level)


@contextlib.contextmanager
def log_queries():
    handler = start_log_queries()
    try:
        yield
    finally:
        stop_log_queries(handler)


class SqliteMaxVariableMixin(object):

    @contextlib.contextmanager
    def assertNoMaxVariables(self):
        handler = start_log_queries(record_mode=True)
        try:
            yield
        finally:
            stop_log_queries(handler)
            for line in handler.records:
                self.assertFalse(line.count("?") > 999,
                                 "too much variables in " + line)

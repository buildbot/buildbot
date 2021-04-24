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
# Portions Copyright Buildbot Team Members

import threading
from queue import Queue

from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log


class UndoableQueue(Queue):
    def unget(self, x):
        with self.mutex:
            self.queue.appendleft(x)


class _TerminateRequest:
    pass


class ConnectableThreadQueue(threading.Thread):
    """
    This provides worker thread that is processing work given via execute_in_thread() method.
    The return value of the function passed to execute_in_thread() is returned via Deferred.
    All work is performed in a "connection", which is established in create_connection() which
    is intended to be overridden by user. The user is expected to return an opaque connection
    object from create_connection(). create_connection() must not throw exceptions.
    The connection is from the user-side closed by calling close_connection().

    When the thread is joined, it will execute all currently pending items and call
    on_close_connection() if needed to close the connection. Any work submitted after join() is
    called will be ignored.
    """
    def __init__(self):
        self._queue = UndoableQueue()
        self._conn = None
        super().__init__(daemon=True)
        self.connecting = False
        self.start()

    def join(self, *args, **kwargs):
        self.execute_in_thread(_TerminateRequest())
        super().join(*args, **kwargs)

    def execute_in_thread(self, cb, *args, **kwargs):
        d = defer.Deferred()
        self._queue.put((d, cb, args, kwargs))
        return d

    @property
    def conn(self):
        return self._conn

    def close_connection(self):
        self._conn = None
        self.connecting = False

    def on_close_connection(self, conn):
        # override to perform any additional connection closing tasks
        self.close_connection()

    def create_connection(self):
        # override to create a new connection
        raise NotImplementedError()

    def run(self):
        while True:
            result_d, next_operation, args, kwargs = self._queue.get()

            if isinstance(next_operation, _TerminateRequest):
                self._queue.task_done()
                reactor.callFromThread(result_d.callback, None)
                break

            if not self._conn:
                self.connecting = True
                self._queue.unget((result_d, next_operation, args, kwargs))
                try:
                    self._conn = self.create_connection()
                except Exception as e:
                    log.err(e, "Exception received from ConnectableThreadQueue.create_connection()")
                self.connecting = False
                continue

            try:
                result = next_operation(*args, **kwargs)
                reactor.callFromThread(result_d.callback, result)
            except Exception as e:
                reactor.callFromThread(result_d.errback, e)
            self._queue.task_done()

        if self._conn is not None:
            self.on_close_connection(self._conn)

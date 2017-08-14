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
from future.utils import itervalues
from future.utils import text_type

import re

from twisted.internet import defer
from twisted.python import log

from buildbot import util
from buildbot.util import lineboundaries


class Log(object):
    _byType = {}

    def __init__(self, master, name, type, logid, decoder):
        self.type = type
        self.logid = logid
        self.master = master
        self.name = name

        self.subPoint = util.subscription.SubscriptionPoint("%r log" % (name,))
        self.subscriptions = {}
        self.finished = False
        self.finishWaiters = []
        self.lock = defer.DeferredLock()
        self.decoder = decoder

    @staticmethod
    def _decoderFromString(cfg):
        """
        Return a decoder function.
        If cfg is a string such as 'latin-1' or u'latin-1',
        then we return a new lambda, s.decode().
        If cfg is already a lambda or function, then we return that.
        """
        if isinstance(cfg, (bytes, str)):
            return lambda s: s.decode(cfg, 'replace')
        return cfg

    @classmethod
    def new(cls, master, name, type, logid, logEncoding):
        type = text_type(type)
        try:
            subcls = cls._byType[type]
        except KeyError:
            raise RuntimeError("Invalid log type %r" % (type,))
        decoder = Log._decoderFromString(logEncoding)
        return subcls(master, name, type, logid, decoder)

    def getName(self):
        return self.name

    # subscriptions

    def subscribe(self, callback):
        return self.subPoint.subscribe(callback)

    # adding lines

    @defer.inlineCallbacks
    def addRawLines(self, lines):
        # used by subclasses to add lines that are already appropriately
        # formatted for the log type, and newline-terminated
        assert lines[-1] == '\n'
        assert not self.finished
        yield self.lock.run(lambda: self.master.data.updates.appendLog(self.logid, lines))

    # completion

    def isFinished(self):
        return self.finished

    def waitUntilFinished(self):
        d = defer.Deferred()
        if self.finished:
            d.succeed(None)
        else:
            self.finishWaiters.append(d)
        return d

    @defer.inlineCallbacks
    def finish(self):
        assert not self.finished

        def fToRun():
            self.finished = True
            return self.master.data.updates.finishLog(self.logid)
        yield self.lock.run(fToRun)
        # notify subscribers *after* finishing the log
        self.subPoint.deliver(None, None)

        # notify those waiting for finish
        for d in self.finishWaiters:
            d.callback(None)

        # start a compressLog call but don't make our caller wait for
        # it to complete
        d = self.master.data.updates.compressLog(self.logid)
        d.addErrback(
            log.err, "while compressing log %d (ignored)" % self.logid)


class PlainLog(Log):

    def __init__(self, master, name, type, logid, decoder):
        super(PlainLog, self).__init__(master, name, type, logid, decoder)

        def wholeLines(lines):
            if not isinstance(lines, text_type):
                lines = self.decoder(lines)
            self.subPoint.deliver(None, lines)
            return self.addRawLines(lines)
        self.lbf = lineboundaries.LineBoundaryFinder(wholeLines)

    def addContent(self, text):
        # add some text in the log's default stream
        return self.lbf.append(text)

    @defer.inlineCallbacks
    def finish(self):
        yield self.lbf.flush()
        yield super(PlainLog, self).finish()


class TextLog(PlainLog):

    pass


Log._byType['t'] = TextLog


class HtmlLog(PlainLog):

    pass


Log._byType['h'] = HtmlLog


class StreamLog(Log):

    pat = re.compile('^', re.M)

    def __init__(self, step, name, type, logid, decoder):
        super(StreamLog, self).__init__(step, name, type, logid, decoder)
        self.lbfs = {}

    def _getLbf(self, stream):
        try:
            return self.lbfs[stream]
        except KeyError:
            def wholeLines(lines):
                if not isinstance(lines, text_type):
                    lines = self.decoder(lines)
                # deliver the un-annotated version to subscribers
                self.subPoint.deliver(stream, lines)
                # strip the last character, as the regexp will add a
                # prefix character after the trailing newline
                return self.addRawLines(self.pat.sub(stream, lines)[:-1])
            lbf = self.lbfs[stream] = \
                lineboundaries.LineBoundaryFinder(wholeLines)
            return lbf

    def addStdout(self, text):
        return self._getLbf('o').append(text)

    def addStderr(self, text):
        return self._getLbf('e').append(text)

    def addHeader(self, text):
        return self._getLbf('h').append(text)

    @defer.inlineCallbacks
    def finish(self):
        for lbf in itervalues(self.lbfs):
            yield lbf.flush()
        yield super(StreamLog, self).finish()


Log._byType['s'] = StreamLog

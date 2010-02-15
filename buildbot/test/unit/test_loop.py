# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is Mozilla-specific Buildbot steps.
#
# The Initial Developer of the Original Code is
# Mozilla Foundation.
# Portions created by the Initial Developer are Copyright (C) 2009
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#   Brian Warner <warner@lothar.com>
#
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
#
# ***** END LICENSE BLOCK *****

import time
from twisted.trial import unittest
from twisted.internet import reactor, defer
from twisted.application import service
from twisted.python import log
from buildbot import loop

class NotInSingleFileError(Exception):
    pass

class SingleFileChecker:
    def __init__(self):
        self.current = None
    def enter(self, who):
        if self.current:
            log.err("Error, %s was running, then %s entered"
                    % (self.current, who))
            raise NotInSingleFileError()
        self.current = who
    def exit(self, who):
        if who != self.current:
            log.err("Error, %s was running, but %s exited"
                    % (self.current, who))
            raise NotInSingleFileError()
        self.current = None

class Soon(service.Service):
    count = 0
    def run(self):
        self.checker.enter(self)
        d = defer.Deferred()
        reactor.callLater(0, d.callback, None)
        d.addCallback(self._done)
        return d
    def _done(self, res):
        self.count = self.count + 1
        self.checker.exit(self)
        return res
class SoonAndAgain(Soon):
    def _done(self, res):
        if not self.count:
            self.loop.trigger()
        self.count = self.count + 1
        self.checker.exit(self)
        return res

class Now(service.Service):
    count = 0
    def run(self):
        self.checker.enter(self)
        self.count = self.count + 1
        self.checker.exit(self)
        return None

class Loop(unittest.TestCase):
    def test_create(self):
        # SoonAndAgain will re-trigger the loop on its first run, so the
        # entire loop should run twice, which means every Processor should
        # have count==2 at the end
        l = loop.Loop()
        l.startService()
        c = SingleFileChecker()
        processors = [Soon(), Soon(), SoonAndAgain(), Now()]
        for p in processors:
            p.checker = c
            p.loop = l
            l.add(p.run)
        d = l.when_quiet()
        l.trigger()
        def _check(res):
            for p in processors:
                self.failUnlessEqual(p.count, 2)
        d.addCallback(_check)
        return d

    def test_done(self):
        done = []
        l = loop.Loop()
        l.startService()
        # monkey-patch the instance to have a 'loop_done' method
        # which just modifies 'done' to indicate that it was called
        l.loop_done = lambda: done.append(1)
        c = SingleFileChecker()
        processors = [Soon(), Soon(), SoonAndAgain(), Now()]
        for p in processors:
            p.checker = c
            p.loop = l
            l.add(p.run)
        d = l.when_quiet()
        l.trigger()
        def _check(res):
            for p in processors:
                self.failUnlessEqual(p.count, 2)
            self.failUnlessEqual(len(done), 1)
        d.addCallback(_check)
        return d

    def test_delegate(self):
        # Test the DelegateLoop class, performing about the same test as above
        processors = [Soon(), Soon(), SoonAndAgain(), Now()]
        def get_processors():
            return [p.run for p in processors]
        l = loop.DelegateLoop(get_processors)
        l.startService()
        c = SingleFileChecker()
        for p in processors:
            p.checker = c
            p.loop = l
        d = l.when_quiet()
        l.trigger()
        def _check(res):
            for p in processors:
                self.failUnlessEqual(p.count, 2)
        d.addCallback(_check)
        return d

    def test_merge(self):
        l = loop.Loop()
        l.startService()
        c = SingleFileChecker()
        processors = [Soon(), Soon()]
        for p in processors:
            p.checker = c
            p.loop = l
            l.add(p.run)
        d = l.when_quiet()
        # multiple triggers in the same reactor turn will be merged
        l.trigger()
        l.trigger()
        l.trigger()
        def _check(res):
            for p in processors:
                self.failUnlessEqual(p.count, 1)
        d.addCallback(_check)
        return d

class Service(unittest.TestCase):
    def test_create(self):
        s = loop.MultiServiceLoop()
        c = SingleFileChecker()
        processors = [Soon(), Soon(), SoonAndAgain(), Now()]
        for p in processors:
            p.checker = c
            p.loop = s
            p.setServiceParent(s)
        d = s.when_quiet()
        s.startService()
        for p in processors:
            self.failUnlessEqual(bool(p.running), True)
        s.trigger()
        def _check(res):
            for p in processors:
                self.failUnlessEqual(p.count, 2)
        d.addCallback(_check)
        return d

EPSILON = 0.1
class Later(service.Service):
    count = 0
    wakeup = None
    def __init__(self, delay=None):
        self.delay = delay
    def run(self):
        self.checker.enter(self)
        d = defer.Deferred()
        if self.wakeup is None:
            self.wakeup = time.time() + self.delay
        alarm = None
        if time.time() < self.wakeup:
            alarm = self.wakeup + EPSILON
        reactor.callLater(0, d.callback, alarm)
        d.addCallback(self._done)
        return d
    def _done(self, res):
        self.count = self.count + 1
        self.checker.exit(self)
        return res

class Sleep(unittest.TestCase):
    def test_create(self):
        l = loop.Loop()
        l.startService()
        l.OCD_MINIMUM_DELAY = 1.0
        c = SingleFileChecker()
        processors = [Soon(), Later(1.0), SoonAndAgain(), Now()]
        # what should happen:
        #  all four fire
        #   Later sets a 1s+e timer
        #   SoonAndAgain sets everything to run again
        #  all four fire (due to the SoonAndAgain trigger)
        #   Later sets a 1s+e-small timer
        #  Later is run, once
        # so Later is run three times, everything else should be run twice
        for p in processors:
            p.checker = c
            p.loop = l
            l.add(p.run)
        d = l.when_quiet()
        l.trigger()
        def _check(res):
            for p in processors:
                if isinstance(p, Later):
                    self.failUnlessEqual(p.count, 3)
                else:
                    self.failUnlessEqual(p.count, 2)
        d.addCallback(_check)
        return d

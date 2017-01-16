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

from twisted.internet import defer
from twisted.python import failure


class Expect(object):

    """
    An expected instantiation of RunProcess.  Usually used within a RunProcess
    expect invocation:

        rp.expect(
            Expect("echo", "bar", usePTY=False)
             + { 'stdout' : 'hello!!' }
             + { 'rc' : 13 }
             + 13 # for a callback with rc=13; or
             + Failure(..), # for a failure
            Expect(..) + .. ,
            ...
        )

    Note that the default values are accepted for all keyword arguments if they
    are not omitted.
    """

    def __init__(self, command, workdir, **kwargs):
        self.kwargs = dict(command=command, workdir=workdir)
        self.kwargs.update(kwargs)

        self.result = None
        self.status_updates = []

    def __add__(self, other):
        if isinstance(other, dict):
            self.status_updates.append(other)
        elif isinstance(other, int):
            self.result = ('c', other)
        elif isinstance(other, failure.Failure):
            self.result = ('e', other)
        else:
            raise ValueError("invalid expectation '%r'" % (other,))
        return self

    def __str__(self):
        other_kwargs = self.kwargs.copy()
        del other_kwargs['command']
        del other_kwargs['workdir']
        return "Command: %s\n  workdir: %s\n  kwargs: %s\n  result: %s\n" % (
            self.kwargs['command'], self.kwargs['workdir'],
            other_kwargs, self.result)


class FakeRunProcess(object):

    """
    A fake version of L{buildbot_worker.runprocess.RunProcess} which will
    simulate running external processes without actually running them (which is
    very fragile in tests!)

    This class is first programmed with the set of instances that are expected,
    and with their expected results.  It will raise an AssertionError if the
    expected behavior is not seen.

    Note that this handles sendStderr/sendStdout and keepStderr/keepStdout properly.
    """

    @classmethod
    def expect(cls, *expectations):
        """
        Set the expectations for this test run
        """
        cls._expectations = list(expectations)
        # list the first expectation last, so we can pop it
        cls._expectations.reverse()

    @classmethod
    def test_done(cls):
        """
        Indicate that this test is finished; if any expected instantiations
        have not taken place, this will raise the appropriate AssertionError.
        """
        if cls._expectations:
            raise AssertionError("%d expected instances not created" % len(cls._expectations))
        del cls._expectations

    def __init__(self, builder, command, workdir, **kwargs):
        kwargs['command'] = command
        kwargs['workdir'] = workdir

        # the default values for the constructor kwargs; if we got a default
        # value in **kwargs and didn't expect anything, well count that as OK
        default_values = dict(environ=None,
                              sendStdout=True, sendStderr=True, sendRC=True,
                              timeout=None, maxTime=None, sigtermTime=None, initialStdin=None,
                              keepStdout=False, keepStderr=False,
                              logEnviron=True, logfiles={}, usePTY=False)

        if not self._expectations:
            raise AssertionError("unexpected instantiation: %s" % (kwargs,))
        exp = self._exp = self._expectations.pop()
        if exp.kwargs != kwargs:
            msg = []
            # pylint: disable=consider-iterating-dictionary
            for key in sorted(list(set(exp.kwargs.keys()) | set(kwargs.keys()))):
                if key not in exp.kwargs:
                    if key in default_values:
                        if default_values[key] == kwargs[key]:
                            continue  # default values are expected
                        msg.append('%s: expected default (%r),\n  got %r' %
                                   (key, default_values[key], kwargs[key]))
                    else:
                        msg.append('%s: unexpected arg, value = %r' % (key, kwargs[key]))
                elif key not in kwargs:
                    msg.append('%s: did not get expected arg' % (key,))
                elif exp.kwargs[key] != kwargs[key]:
                    msg.append('%s: expected %r,\n  got %r' % (key, exp.kwargs[key], kwargs[key]))
            if msg:
                msg.insert(
                    0,
                    'did not get expected __init__ arguments for\n {0}'.format(
                        " ".join(map(repr, kwargs.get('command',
                                                      ['unknown command'])))))
                self._expectations[:] = []  # don't expect any more instances, since we're failing
                raise AssertionError("\n".join(msg))

        self._builder = builder
        self.stdout = ''
        self.stderr = ''

    def start(self):
        # figure out the stdio-related parameters
        keepStdout = self._exp.kwargs.get('keepStdout', False)
        keepStderr = self._exp.kwargs.get('keepStderr', False)
        sendStdout = self._exp.kwargs.get('sendStdout', True)
        sendStderr = self._exp.kwargs.get('sendStderr', True)
        if keepStdout:
            self.stdout = ''
        if keepStderr:
            self.stderr = ''
        finish_immediately = True

        # send the updates, accounting for the stdio parameters
        for upd in self._exp.status_updates:
            if 'stdout' in upd:
                if keepStdout:
                    self.stdout += upd['stdout']
                if not sendStdout:
                    del upd['stdout']
            if 'stderr' in upd:
                if keepStderr:
                    self.stderr += upd['stderr']
                if not sendStderr:
                    del upd['stderr']
            if 'wait' in upd:
                finish_immediately = False
                continue  # don't send this update
            if not upd:
                continue
            self._builder.sendUpdate(upd)

        d = self.run_deferred = defer.Deferred()

        if finish_immediately:
            self._finished()

        return d

    def _finished(self):
        if self._exp.result[0] == 'e':
            self.run_deferred.errback(self._exp.result[1])
        else:
            self.run_deferred.callback(self._exp.result[1])

    def kill(self, reason):
        self._builder.sendUpdate({'hdr': 'killing'})
        self._builder.sendUpdate({'rc': -1})
        self.run_deferred.callback(-1)

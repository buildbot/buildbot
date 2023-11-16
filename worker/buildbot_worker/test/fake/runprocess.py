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
        self.kwargs = {"command": command, "workdir": workdir}
        self.kwargs.update(kwargs)

        self.result = None
        self.status_updates = []

    def __str__(self):
        other_kwargs = self.kwargs.copy()
        del other_kwargs['command']
        del other_kwargs['workdir']
        return "Command: {0}\n  workdir: {1}\n  kwargs: {2}\n  result: {3}\n".format(
            self.kwargs['command'], self.kwargs['workdir'],
            other_kwargs, self.result)

    def update(self, key, value):
        self.status_updates.append([(key, value)])
        return self

    def updates(self, updates):
        self.status_updates.append((updates))
        return self

    def exit(self, rc_code):
        self.result = ('c', rc_code)
        return self

    def exception(self, error):
        self.result = ('e', error)
        return self


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
            raise AssertionError(("{0} expected instances not created"
                                  ).format(len(cls._expectations)))
        del cls._expectations

    def __init__(self, command_id, command, workdir, unicode_encoding, send_update, **kwargs):
        kwargs['command'] = command
        kwargs['workdir'] = workdir

        # the default values for the constructor kwargs; if we got a default
        # value in **kwargs and didn't expect anything, well count that as OK
        default_values = {
            "environ": None,
            "sendStdout": True,
            "sendStderr": True,
            "sendRC": True,
            "timeout": None,
            "maxTime": None,
            "sigtermTime": None,
            "initialStdin": None,
            "keepStdout": False,
            "keepStderr": False,
            "logEnviron": True,
            "logfiles": {},
            "usePTY": False
        }

        if not self._expectations:
            raise AssertionError("unexpected instantiation: {0}".format(kwargs))
        exp = self._exp = self._expectations.pop()
        if exp.kwargs != kwargs:
            msg = []
            # pylint: disable=consider-iterating-dictionary
            for key in sorted(list(set(exp.kwargs.keys()) | set(kwargs.keys()))):
                if key not in exp.kwargs:
                    if key in default_values:
                        if default_values[key] == kwargs[key]:
                            continue  # default values are expected
                        msg.append('{0}: expected default ({1!r}),\n  got {2!r}'.format(
                                   key, default_values[key], kwargs[key]))
                    else:
                        msg.append('{0}: unexpected arg, value = {1!r}'.format(key, kwargs[key]))
                elif key not in kwargs:
                    msg.append('{0}: did not get expected arg'.format(key))
                elif exp.kwargs[key] != kwargs[key]:
                    msg.append('{0}: expected {1!r},\n  got {2!r}'.format(key, exp.kwargs[key],
                                                                          kwargs[key]))
            if msg:
                msg.insert(
                    0,
                    'did not get expected __init__ arguments for\n {0}'.format(
                        " ".join(map(repr, kwargs.get('command',
                                                      ['unknown command'])))))
                self._expectations[:] = []  # don't expect any more instances, since we're failing
                raise AssertionError("\n".join(msg))

        self.send_update = send_update
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

        for update in self._exp.status_updates:
            data = []
            for key, value in update:
                if key == 'stdout':
                    if keepStdout:
                        self.stdout += value
                    if not sendStdout:
                        continue  # don't send this update
                if key == 'stderr':
                    if keepStderr:
                        self.stderr += value
                    if not sendStderr:
                        continue
                if key == 'wait':
                    finish_immediately = False
                    continue
                data.append((key, value))
            self.send_update(data)

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
        self.send_update([('header', 'killing')])
        self.send_update([('rc', -1)])
        self.run_deferred.callback(-1)

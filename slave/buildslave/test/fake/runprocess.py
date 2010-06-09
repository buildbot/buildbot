from twisted.python import failure
from twisted.internet import defer

class Expect:
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
            self.result = ( 'c', other )
        elif isinstance(other, failure.Failure):
            self.result = ( 'e', other )
        else:
            raise ValueError("invalid expectation '%r'" % (other,))
        return self

class FakeRunProcess:
    """
    A fake version of L{buildslave.runprocess.RunProcess} which will
    simulate running external processes without actually running them (which is
    very fragile in tests!)

    This class is first programmed with the set of instances that are expected,
    and with their expected results.  It will raise an AssertionError if the
    expected behavior is not seen.
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
                 timeout=None, maxTime=None, initialStdin=None,
                 keepStdinOpen=False, keepStdout=False, keepStderr=False,
                 logEnviron=True, logfiles={}, usePTY="slave-config")

        if not self._expectations:
            raise AssertionError("unexpected instantiation: %s" % (kwargs,))
        exp = self._expectations.pop()
        if exp.kwargs != kwargs:
            msg = [ ]
            for key in sorted(list(set(exp.kwargs.keys()) | set(kwargs.keys()))):
                if key not in exp.kwargs:
                    if key in default_values:
                        if default_values[key] == kwargs[key]:
                            continue # default values are expected
                        msg.append('%s: expected default (%r), got %r' %
                                    (key, default_values[key], kwargs[key]))
                    else:
                        msg.append('%s: unexpected arg, value = %r' % (key, kwargs[key]))
                elif key not in kwargs:
                    msg.append('%s: did not get expected arg' % (key,))
                elif exp.kwargs[key] != kwargs[key]:
                    msg.append('%s: expected %r, got %r' % (key, exp.kwargs[key], kwargs[key]))
            if msg:
                msg.insert(0, 'did not get expected __init__ arguments:')
                raise AssertionError("\n".join(msg))

        self._builder = builder
        self._status_updates = exp.status_updates
        self._result = exp.result

    def start(self):
        # send the updates and return an already-fired deferred
        for upd in self._status_updates:
            self._builder.sendUpdate(upd)
        if self._result[0] == 'e':
            return defer.fail(self._result[1])
        else:
            return defer.succeed(self._result[1])

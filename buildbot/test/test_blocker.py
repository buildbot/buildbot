from twisted.trial import unittest
from twisted.internet import reactor, defer

from buildbot.test.runutils import RunMixin
from buildbot.sourcestamp import SourceStamp
from buildbot.process.base import BuildRequest
from buildbot.steps import blocker

class TestBlockerTrivial(unittest.TestCase):
    """
    Trivial test cases that don't require a whole BuildMaster/BotMaster/
    Builder/Build object graph.
    """

    def assertRaises(self, exception, callable, *args, **kwargs):
        """
        Variation on default assertRaises() that takes either an exception class
        or an exception object.  For an exception object, it compares
        str() values of the expected exception and the actual raised exception.
        """
        if isinstance(exception, type(Exception)): # it's an exception class
            unittest.TestCase.assertRaises(self, exception, callable, *args, **kwargs)
        elif isinstance(exception, Exception):
            exc_name = exception.__class__.__name__
            try:
                callable(*args, **kwargs)
            except exception.__class__, actual:
                self.assertEquals(
                    str(exception), str(actual),
                    "expected %s: %r, but got %r"
                    % (exc_name, str(exception), str(actual)))
            else:
                self.fail("%s not raised" % exc_name)
        else:
            raise TypeError("'exception' must be an exception class "
                            "or exception object (not %r)"
                            % exception)

    def testConstructor(self):
        # upstreamSteps must be supplied...
        self.assertRaises(ValueError("you must supply upstreamSteps"),
                          blocker.Blocker)
        # ...and must be a non-empty list
        self.assertRaises(ValueError("upstreamSteps must be a non-empty list"),
                          blocker.Blocker, upstreamSteps=[])

        # builder name and step name do not matter to constructor
        bstep = blocker.Blocker(upstreamSteps=[("b1", "s1"), ("b1", "s3")])

        # test construction of _fullnames
        self.assertEqual(["b1:s1,", "b1:s3"], bstep._fullnames)

        # test validation of idlePolicy arg
        self.assertRaises(ValueError, blocker.Blocker, idlePolicy="foo")

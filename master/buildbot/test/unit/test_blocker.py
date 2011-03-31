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

from twisted.trial import unittest

from buildbot.status import builder
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
            unittest.TestCase.assertRaises(
                self, exception, callable, *args, **kwargs)
        elif isinstance(exception, Exception):     # it's an exception object
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
        blocker.Blocker(upstreamSteps=[("b1", "s1"), ("b1", "s3")])

        # test validation of idlePolicy arg
        self.assertRaises(ValueError, blocker.Blocker, idlePolicy="foo")

    def testFullnames(self):
        bstep = blocker.Blocker(upstreamSteps=[("b1", "s1")])
        self.assertEqual(["(b1:s1)"], bstep._getFullnames())

        bstep = blocker.Blocker(upstreamSteps=[("b1", "s1"), ("b1", "s3")])
        self.assertEqual(["(b1:s1,", "b1:s3)"], bstep._getFullnames())

        bstep = blocker.Blocker(upstreamSteps=[("b1", "s1"), 
                                               ("b1", "s3"), 
                                               ("b2", "s1")])
        self.assertEqual(["(b1:s1,", "b1:s3,", "b2:s1)"], bstep._getFullnames())

    def testStatusText(self):
        bstep = blocker.Blocker(
            name="block-something",
            upstreamSteps=([("builder1", "step1"), ("builder3", "step4")]),
            )

        # A Blocker can be in various states, each of which has a
        # distinct status text:
        #   1) blocking, ie. waiting for upstream builders/steps
        #   2) successfully done (upstream steps all succeeded)
        #   3) failed (at least upstream step failed)
        #   4) timed out (waited too long)

        self.assertEqual(["block-something:",
                          "blocking on",
                          "(builder1:step1,",
                          "builder3:step4)"],
                         bstep._getBlockingStatusText())
        self.assertEqual(["block-something:",
                          "upstream success",
                          "after 4.3 sec"],
                         bstep._getFinishStatusText(builder.SUCCESS, 4.3))
        self.assertEqual(["block-something:",
                          "upstream failure",
                          "after 11.0 sec",
                          "(builder1:step1,",
                          "builder3:step4)"],
                         bstep._getFinishStatusText(builder.FAILURE, 11.0))

        bstep.timeout = 1.5
        self.assertEqual(["block-something:",
                          "timed out",
                          "(1.5 sec)"],
                         bstep._getTimeoutStatusText())


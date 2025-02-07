.. bb:reportgen:: BuildSetCombinedStatusGenerator

.. _Reportgen-BuildSetCombinedStatusGenerator:

BuildSetCombinedStatusGenerator
+++++++++++++++++++++++++++++++

.. py:class:: buildbot.reporters.BuildSetCombinedStatusGenerator

This report generator sends a message about a buildset.

Message formatter is invoked only once for all builds in the buildset.

It is very similar to :bb:reportgen:`BuildSetCombinedStatusGenerator` but invokes message
formatters for each matching build in the buildset. The collected messages are then joined and sent
as a single message.


A buildset without any builds is useful as a means to report to code review system that a
particular code version does not need to be tested.  For example in cases when a pull request is
updated with the only difference being commit message being changed.

The following parameters are supported:

``message_formatter``
    (instance of ``reporters.MessageFormatter``)
    This is an instance of the ``reporters.MessageFormatter`` class that will be used to generate
    message for the buildset.

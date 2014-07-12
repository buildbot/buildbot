Logs
====

.. py:module:: buildbot.process.log

.. py:class:: Log

    This class handles write-only access to log files from running build steps.
    It does not provide an interface for reading logs - such access should occur directly through the Data API.

    Instances of this class can only be created by the :py:meth:`~buildbot.process.buildstep.BuildStep.addLog` method of a build step.

    .. py:attribute:: name

        The name of the log.

    .. py:attribute:: type

        The type of the log, represented as a single character.
        See :bb:rtype:`logchunk` for details.

    .. py:attribute:: logid

        The ID of the logfile.

    .. py:attribute:: decoder

        A callable used to decode bytestrings.
        See :bb:cfg:`logEncoding`.

    .. py:method:: subscribe(receiver)

        :param callable receiver: the function to call

        Register ``receiver`` to be called with line-delimited chunks of log data.
        The callable is invoked as ``receiver(stream, chunk)``, where the stream is indicated by a single character, or None for logs without streams.
        The chunk is a single string containing an arbitrary number of log lines, and terminated with a newline.
        When the logfile is finished, ``receiver`` will be invoked with ``None`` for both arguments.

        The callable cannot return a Deferred.
        If it must perform some asynchronous operation, it will need to handle its own Deferreds, and be aware that multiple overlapping calls may occur.

        Note that no "rewinding" takes place: only log content added after the call to ``subscribe`` will be supplied to ``receiver``.

    .. py:method:: finish()

        :returns: Deferred

        This method indicates that the logfile is finished.
        No further additions will be permitted.

In use, callers will receive a subclass with methods appropriate for the log type:

.. py:class:: TextLog

    .. py:method:: addContent(text):

        :param text: log content
        :returns: Deferred

        Add the given data to the log.
        The data need not end on a newline boundary.


.. py:class:: HTMLLog

    .. py:method:: addContent(text):

        :param text: log content
        :returns: Deferred

        Same as :py:meth:`TextLog.addContent`.

.. py:class:: StreamLog

    This class handles logs containing three interleaved streams: stdout, stderr, and header.
    The resulting log maintains data distinguishing these streams, so they can be filtered or displayed in different colors.
    This class is used to represent the stdio log in most steps.

    .. py:method:: addStdout(text)

        :param text: log content
        :returns: Deferred

        Add content to the stdout stream.
        The data need not end on a newline boundary.

    .. py:method:: addStderr(text)

        :param text: log content
        :returns: Deferred

        Add content to the stderr stream.
        The data need not end on a newline boundary.

    .. py:method:: addHeader(text)

        :param text: log content
        :returns: Deferred

        Add content to the header stream.
        The data need not end on a newline boundary.

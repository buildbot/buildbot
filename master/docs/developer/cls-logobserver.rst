LogObservers
============

.. py:module:: buildbot.process.logobserver

.. py:class:: LogObserver

    This is a base class for objects which receive logs from worker commands as they are produced.
    It does not provide an interface for reading logs - such access should occur directly through the Data API.

    See :ref:`Adding-LogObservers` for help creating and using a custom log observer.

    The three methods that subclasses may override follow.
    None of these methods may return a Deferred.
    It is up to the callee to handle any asynchronous operations.
    Subclasses may also override the constructor, with no need to call :py:class:`LogObserver`'s constructor.

    .. py:method:: outReceived(data):

        :param unicode data: received data

        This method is invoked when a "chunk" of data arrives in the log.
        The chunk contains one or more newline-terminated unicode lines.
        For stream logs (e.g., ``stdio``), output to stderr generates a call to :py:meth:`errReceived`, instead.

    .. py:method:: errReceived(data):

        :param unicode data: received data

        This method is similar to :py:meth:`outReceived`, but is called for output to stderr.

    .. py:method:: headerReceived(data):

        :param unicode data: received data

        This method is similar to :py:meth:`outReceived`, but is called for header output.

    .. py:method:: finishReceived()

        This method is invoked when the observed log is finished.

.. py:class:: LogLineObserver

    This subclass of :py:class:`LogObserver` calls its subclass methods once for each line, instead of once per chunk.

    .. py:method:: outLineReceived(line):

        :param unicode line: received line, without newline

        Like :py:meth:`~LogObserver.outReceived`, this is called once for each line of output received.
        The argument does not contain the trailing newline character.

    .. py:method:: errLineReceived(line):

        :param unicode line: received line, without newline

        Similar to :py:meth:`~LogLineObserver.outLineReceived`, but for stderr.

    .. py:method:: headerLineReceived(line):

        :param unicode line: received line, without newline

        Similar to :py:meth:`~LogLineObserver.outLineReceived`, but for header output..

    .. py:method:: finishReceived()

        This method, inherited from :py:class:`LogObserver`, is invoked when the observed log is finished.

.. py:class:: LineConsumerLogObserver

    This subclass of :py:class:`LogObserver` takes a generator function and "sends" each line to that function.
    This allows consumers to be written as stateful Python functions, e.g., ::

        def logConsumer(self):
            while True:
                stream, line = yield
                if stream == 'o' and line.startswith('W'):
                    self.warnings.append(line[1:])

        def __init__(self):
            ...
            self.warnings = []
            self.addLogObserver('stdio', logobserver.LineConsumerLogObserver(self.logConsumer))

    Each ``yield`` expression evaluates to a tuple of (stream, line), where the stream is one of 'o', 'e', or 'h' for stdout, stderr, and header, respectively.
    As with any generator function, the ``yield`` expression will raise a ``GeneratorExit`` exception when the generator is complete.
    To do something after the log is finished, just catch this exception (but then re-raise it or return) ::

        def logConsumer(self):
            while True:
                try:
                    stream, line = yield
                    if stream == 'o' and line.startswith('W'):
                        self.warnings.append(line[1:])
                except GeneratorExit:
                    self.warnings.sort()
                    return

    .. warning::

        This use of generator functions is a simple Python idiom first described in `PEP 342 <https://www.python.org/dev/peps/pep-0342/>`__.
        It is unrelated to the generators used in ``inlineCallbacks``.
        In fact, consumers of this type are incompatible with asynchronous programming, as each line must be processed immediately.

.. py:class:: BufferLogObserver(wantStdout=True, wantStderr=False)

    :param boolean wantStdout: true if stdout should be buffered
    :param boolean wantStderr: true if stderr should be buffered

    This subclass of :py:class:`LogObserver` buffers stdout and/or stderr for analysis after the step is complete.
    This can cause excessive memory consumption if the output is large.

    .. py:method:: getStdout()

        :returns: unicode string

        Return the accumulated stdout.

    .. py:method:: getStderr()

        :returns: unicode string

        Return the accumulated stderr.

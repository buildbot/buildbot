LogObservers
============

.. py:module:: buildbot.process.logobserver

.. py:class:: LogObserver

    This is a base class for objects which receive logs from slave commands as they are produced.
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

    .. py:method:: finishReceived()

        This method, inherited from :py:class:`LogObserver`, is invoked when the observed log is finished.

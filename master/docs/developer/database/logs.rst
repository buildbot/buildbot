Logs connector
~~~~~~~~~~~~~~

.. py:module:: buildbot.db.logs

.. index:: double: Logs; DB Connector Component

.. py:class:: LogsConnectorComponent

    This class handles log data.
    Build steps can have zero or more logs.
    Logs are uniquely identified by name within a step.

    Information about a log, apart from its contents, is represented as a dictionary with the following keys, referred to as a *logdict*:

    * ``id`` (log ID, globally unique)
    * ``stepid`` (step ID, indicating the containing step)
    * ``name`` free-form name of this log
    * ``slug`` (50-identifier for the log, unique within the step)
    * ``complete`` (true if the log is complete and will not receive more lines)
    * ``num_lines`` (number of lines in the log)
    * ``type`` (log type; see below)

    Each log has a type that describes how to interpret its contents.
    See the :bb:rtype:`logchunk` resource type for details.

    A log contains a sequence of newline-separated lines of unicode.
    Log line numbering is zero-based.

    Each line must be less than 64k when encoded in UTF-8.
    Longer lines will be truncated, and a warning will be logged.

    Lines are stored internally in "chunks", and optionally compressed, but the implementation hides these details from callers.

    .. py:method:: getLog(logid)

        :param integer logid: ID of the requested log
        :returns: logdict via Deferred

        Get a log, identified by logid.

    .. py:method:: getLogBySlug(stepid, slug)

        :param integer stepid: ID of the step containing this log
        :param slug: slug of the logfile to retrieve
        :type name: 50-character identifier
        :returns: logdict via Deferred

        Get a log, identified by name within the given step.

    .. py:method:: getLogs(stepid)

        :param integer stepid: ID of the step containing the desired logs
        :returns: list of logdicts via Deferred

        Get all logs within the given step.

    .. py:method:: getLogLines(logid, first_line, last_line)

        :param integer logid: ID of the log
        :param first_line: first line to return
        :param last_line: last line to return
        :returns: see below

        Get a subset of lines for a logfile.

        The return value, via Deferred, is a concatenation of newline-terminated strings.
        If the requested last line is beyond the end of the logfile, only existing lines will be included.
        If the log does not exist, or has no associated lines, this method returns an empty string.

    .. py:method:: addLog(stepid, name, type)

        :param integer stepid: ID of the step containing this log
        :param string name: name of the logfile
        :param slug: slug (unique identifier) of the logfile
        :type slug: 50-character identifier
        :param string type: log type (see above)
        :raises KeyError: if a log with the given slug already exists in the step
        :returns: ID of the new log, via Deferred

        Add a new log file to the given step.

    .. py:method:: appendLog(logid, content)

        :param integer logid: ID of the requested log
        :param string content: new content to be appended to the log
        :returns: tuple of first and last line numbers in the new chunk, via Deferred

        Append content to an existing log.
        The content must end with a newline.
        If the given log does not exist, the method will silently do nothing.

        It is not safe to call this method more than once simultaneously for the same ``logid``.

    .. py:method:: finishLog(logid)

        :param integer logid: ID of the log to mark complete
        :returns: Deferred

        Mark a log as complete.

        Note that no checking for completeness is performed when appending to a log.
        It is up to the caller to avoid further calls to ``appendLog`` after ``finishLog``.

    .. py:method:: compressLog(logid)

        :param integer logid: ID of the log to compress
        :returns: Deferred

        Compress the given log.
        This method performs internal optimizations on a log's chunks to reduce the space used and make read operations more efficient.
        It should only be called for finished logs.
        This method may take some time to complete.

    .. py:method:: deleteOldLogChunks(older_than_timestamp)

        :param integer older_than_timestamp: the logs whose step's ``started_at`` is older than ``older_than_timestamp`` will be deleted.
        :returns: Deferred

        Delete old logchunks (helper for the ``logHorizon`` policy).
        Old logs have their logchunks deleted from the database, but they keep their ``num_lines`` metadata.
        They have their types changed to 'd', so that the UI can display something meaningful.

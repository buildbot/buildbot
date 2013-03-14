Logchunks
=========

.. bb:rtype:: logchunk

    :attr integer logid: the ID of log containing this chunk
    :attr integer firstline: zero-based line number of the first line in this chunk
    :attr string content: content of the chunk

    A logchunk represents a contiguous sequence of lines in a logfile.
    Logs are not individually addressible in the data API; instead, they must be requested by line number range.
    Many logchunk resources will contain the same line.

    The chunk contents is represented as a single unicode string.
    This string is the concatenation of each newline terminated-line.

    Each log has a type, as identified by the "type" field of the corresponding :bb:rtype:`log`.
    While all logs are sequences of unicode lines, the type gives additional information fo interpreting the contents.
    The defined types are:

     * ``t`` -- text, a simple sequence of lines of text
     * ``s`` -- stdio, like text but with each line tagged with a stream
     * ``h`` -- HTML, represented as plain text

    In the stream type, each line is prefixed by a character giving the stream type for that line.
    The types are ``i`` for input, ``o`` for stdout, ``e`` for stderr, and ``h`` for header.
    The first three correspond to normal UNIX standard streams, while the header stream contains metadata produced by buildbot itself.

    All paths below take ``firstline`` and ``lastline`` indexes to select the desired first and last lines.
    If ``firstline`` is omitted, it is assumed to be 0.
    If ``lastline`` is omitted, it is assumed to be the last line in the log.
    If ``lastline`` is beyond the current end of the log, then the results will be truncated.
    If ``firstline`` and ``lastline`` are invalid, nothing will be returned.

    .. todo::

        .. bb:event:: build.$buildid.step.$number.log.$logid.logchunk.new

            A new chunk has been added to the end of the indicated log.
            The message body does not have a ``content`` key, but does havea ``lastline`` key.

    .. bb:rpath:: /log/:logid/content?firstline=..&lastline=..

        :pathkey integer logid: the ID of the log

    .. bb:rpath:: /step/:stepid/log/:log_name/content?firstline=..&lastline=..

        :pathkey integer stepid: the ID of the step
        :pathkey integer log_name: the name of the log

    .. bb:rpath:: /build/:buildid/step/:step_name/log/:log_name/content?firstline=..&lastline=..

        :pathkey integer buildid: the ID of the build
        :pathkey identifier step_name: the name of the step within the build
        :pathkey identifier log_name: the name of the log

    .. bb:rpath:: /build/:buildid/step/:step_number/log/:log_name/content?firstline=..&lastline=..

        :pathkey integer buildid: the ID of the build
        :pathkey integer step_number: the number of the step within the build
        :pathkey identifier log_name: the name of the log

    .. bb:rpath:: /builder/:builderid/build/:build_number/step/:name/log/:log_name/content?firstline=..&lastline=..

        :pathkey integer builderid: the ID of the builder
        :pathkey integer build_number: the number of the build within the builder
        :pathkey identifier name: the name of the step within the build
        :pathkey identifier log_name: the name of the log

    .. bb:rpath:: /builder/:builderid/build/:build_number/step/:step_number/log/:log_name/content?firstline=..&lastline=..

        :pathkey integer builderid: the ID of the builder
        :pathkey integer build_number: the number of the build within the builder
        :pathkey integer step_number: the number of the step within the build
        :pathkey identifier log_name: the name of the log

Update Methods
--------------

All update methods are available as attributes of ``master.data.logchunks``.

.. py:class:: buildbot.data.logchunks.LogChunkResourceType

    .. py:method:: appendLog(logid, content):

        :param integer logid: the log to which content should be appended
        :param unicode content: the content to append

        Append the given content to the given log.
        The content must end with a newline.

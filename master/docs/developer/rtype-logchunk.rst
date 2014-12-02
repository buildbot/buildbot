Logchunks
=========

.. bb:rtype:: logchunk

    :attr integer logid: the ID of log containing this chunk
    :attr integer firstline: zero-based line number of the first line in this chunk
    :attr string content: content of the chunk

    A logchunk represents a contiguous sequence of lines in a logfile.
    Logs are not individually addressible in the data API; instead, they must be requested by line number range.
    In a strict REST sense, many logchunk resources will contain the same line.

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
    The first three correspond to normal UNIX standard streams, while the header stream contains metadata produced by Buildbot itself.

    The ``offset`` and ``limit`` parameters can be used to select the desired lines.
    These are specified as query parameters via the REST interface, or as arguments to the :py:meth:`~buildbot.data.connector.DataConnector.get` method in Python.
    The result will begin with line ``offset`` (so the resulting ``firstline`` will be equal to the given ``offset``), and will contain up to ``limit`` lines.

    .. note::

        There is no event for a new chunk. Instead, the log resource is updated when new chunks are added, with the new number of lines.
        Consumers can then request those lines, if desired.

    .. bb:rpath:: /log/:logid/contents

        :pathkey integer logid: the ID of the log

    .. bb:rpath:: /step/:stepid/log/:log_slug/contents

        :pathkey integer stepid: the ID of the step
        :pathkey integer log_slug: the slug of the log

    .. bb:rpath:: /build/:buildid/step/:step_name/log/:log_slug/contents

        :pathkey integer buildid: the ID of the build
        :pathkey identifier step_name: the name of the step within the build
        :pathkey identifier log_slug: the slug of the log

    .. bb:rpath:: /build/:buildid/step/:step_number/log/:log_slug/contents

        :pathkey integer buildid: the ID of the build
        :pathkey integer step_number: the number of the step within the build
        :pathkey identifier log_slug: the slug of the log

    .. bb:rpath:: /builder/:builderid/build/:build_number/step/:name/log/:log_slug/contents

        :pathkey integer builderid: the ID of the builder
        :pathkey integer build_number: the number of the build within the builder
        :pathkey identifier name: the name of the step within the build
        :pathkey identifier log_slug: the slug of the log

    .. bb:rpath:: /builder/:builderid/build/:build_number/step/:step_number/log/:log_slug/contents

        :pathkey integer builderid: the ID of the builder
        :pathkey integer build_number: the number of the build within the builder
        :pathkey integer step_number: the number of the step within the build
        :pathkey identifier log_slug: the slug of the log

Raw endpoints
-------------
    Following endpoints allow to get the raw logs for downloading into a file.
    Those endpoints do not provide paging capabilities.
    For stream log types, the type line header characters are dropped.
    'text/plain' is used as the mime type except for html logs, where 'text/html' is used.
    The 'slug' is used as the filename for the resulting download. Some browsers are appending ".txt" or ".html" to this filename according to the mime-type.

    .. bb:rpath:: /log/:logid/raw

        :pathkey integer logid: the ID of the log

    .. bb:rpath:: /step/:stepid/log/:log_slug/raw

        :pathkey integer stepid: the ID of the step
        :pathkey integer log_slug: the slug of the log

    .. bb:rpath:: /build/:buildid/step/:step_name/log/:log_slug/raw

        :pathkey integer buildid: the ID of the build
        :pathkey identifier step_name: the name of the step within the build
        :pathkey identifier log_slug: the slug of the log

    .. bb:rpath:: /build/:buildid/step/:step_number/log/:log_slug/raw

        :pathkey integer buildid: the ID of the build
        :pathkey integer step_number: the number of the step within the build
        :pathkey identifier log_slug: the slug of the log

    .. bb:rpath:: /builder/:builderid/build/:build_number/step/:name/log/:log_slug/raw

        :pathkey integer builderid: the ID of the builder
        :pathkey integer build_number: the number of the build within the builder
        :pathkey identifier name: the name of the step within the build
        :pathkey identifier log_slug: the slug of the log

    .. bb:rpath:: /builder/:builderid/build/:build_number/step/:step_number/log/:log_slug/raw

        :pathkey integer builderid: the ID of the builder
        :pathkey integer build_number: the number of the build within the builder
        :pathkey integer step_number: the number of the step within the build
        :pathkey identifier log_slug: the slug of the log


Update Methods
--------------

Log chunks are updated via :doc:`rtype-log`.


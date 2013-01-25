File Formats
============

Log File Format
---------------

.. py:class:: buildbot.status.logfile.LogFile

The master currently stores each logfile in a single file, which may have a
standard compression applied.

The format is a special case of the netstrings protocol - see
http://cr.yp.to/proto/netstrings.txt.  The text in each netstring
consists of a one-digit channel identifier followed by the data from that
channel.

The formatting is implemented in the LogFile class in
:file:`buildbot/status/logfile.py`, and in particular by the :meth:`merge`
method.



String Encodings
~~~~~~~~~~~~~~~~

Buildbot expects all strings used internally to be valid Unicode strings - not
bytestrings.

Note that Buildbot rarely feeds strings back into external tools in such a way
that those strings must match.  For example, Buildbot does not attempt to
access the filenames specified in a Change.  So it is more important to store
strings in a manner that will be most useful to a human reader (e.g., in
logfiles, web status, etc.) than to store them in a lossless format.

Inputs
++++++

On input, strings should be decoded, if their encoding is known.  Where
necessary, the assumed input encoding should be configurable.  In some cases,
such as filenames, this encoding is not known or not well-defined (e.g., a
utf-8 encoded filename in a latin-1 directory).  In these cases, the input
mechanisms should make a best effort at decoding, and use e.g., the
``errors='replace'`` option to fail gracefully on un-decodable characters.

Outputs
+++++++

At most points where Buildbot outputs a string, the target encoding is known.
For example, the web status can encode to utf-8.  In cases where it is not
known, it should be configurable, with a safe fallback (e.g., ascii with
``errors='replace'``.  For HTML/XML outputs, consider using
``errors='xmlcharrefreplace'`` instead.

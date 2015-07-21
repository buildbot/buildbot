Python3 compatibility
=====================


A good place to start looking for advice to ensure that any code is compatible with both Python-3.x and Python2.6/2.7 is too look at the python-future `cheat sheet <http://python-future.org/compatible_idioms.html>`_ .
Buildbot uses the python-future library to ensure compatibility with both Python2.6/2.7 and Python3.x.

Imports
-------
All ``__future__`` import have to happen at the top of the module, anything else is seen as a syntax error.
All imports from the python-future package should happen below ``__future__`` imports, but before any other.

Yes:

.. code-block:: python

    from __future__ import print_function
    from builtins import basestring

No:

.. code-block:: python

    from twisted.application import internet
    from twisted.spread import pb
    from builtins import str
    from __future__ import print_function

Dictionaries
------------
In python3, ``dict.iteritems`` is no longer available.
While ``dict.items()`` does exist, it can be memory intensive in python2.
For this reason, please use the python.future function ``iteritems()``.

Example:

.. code-block:: python

    d = {"cheese": 4, "bread": 5, "milk": 1}
    for item, num in d.iteritems():
        print("We have {} {}".format(num, item))

should be written as:

.. code-block:: python

    from future.utils import iteritems
    d = {"cheese": 4, "bread": 5, "milk": 1}
    for item, num in iteritems(d):
        print("We have {} {}".format(num, item))

This also applies to the similar methods ``dict.itervalues()`` and ``dict.values()``, which have an equivalent ``itervalues()``.

If a list is required, please use ``list(iteritems(dict))``.
This is for compatibility with the six library.

For iterating over dictionary keys, please use ``for key in dict:``.
For example:

.. code-block:: python

    d = {"cheese": 4, "bread": 5, "milk": 1}
    for item in d:
        print("We have {}".format(item))

Similarly when you want a list of keys:

.. code-block:: python

    keys = list(d)

New-style classes
-----------------
All classes in Python3 are newstyle, so any classes added to the code base must therefore be new-style.
This is done by inheriting ``object``

Old-style:

.. code-block:: python

    class Foo:
        def __init__(self, bar)
            self.bar = bar

new-style:

.. code-block:: python

    class Foo(object):
        def __init__(self, bar)
            self.bar = bar

When creating new-style classes, it is advised to import ``object`` from the builtins module.
The reasoning for this can be read `in the python-future documentation <http://python-future.org/changelog.html#newobject-base-object-defines-fallback-py2-compatible-special-methods>`_

Strings
-------
.. note::
    This has not yet been implemented in the current code base, and will not be strictly adhered to yet.
    But it is important to keep in mind when writing code, that there is a strict distinction between bytestrings and unicode in Python3'


In python2, there is only one type of string.
It can be both unicode and bytestring.
In python3, this is no longer the case.
For this reasons all string must be marked with either ``u''`` or ``b''`` to signify if the string is a unicode string or a bytestring respectively

Example:

.. code-block:: python

    u'this is a unicode string, a string for humans to read'
    b'This is a bytestring, a string for computers to read'


Exceptions
----------
All exceptions should be written with the ``as`` statement.
Before:

.. code-block:: python

    try:
        number = 5 / 0
    except ZeroDivisionError, err:
        print(err.msg)

After:

.. code-block:: python

    try:
        number = 5/0
    except ZeroDivisionError as err:
        print(err.msg)


Basestring
----------
In Python2 there is a basestring type, which both str and unicode inherit.
In Python3, only unicode should be of this type, while bytestrings are ``type(byte)``.

For this reason, we use a builtin form python future.
Before:

.. code-block:: python

    s = "this is a string"
    if(isinstance(basestring)):
        print "This line will run"

After:

.. code-block:: python

    from builtins import str
    unicode_s = u"this is a unicode string"
    byte_s = b"this is a bytestring"

    if(isinstance(unicode_s, str)):
        print("This line will print")
    if(isinstance(byte_s, str):
        print("this line will not print")


Print statements
----------------
Print statements are gone in python3.
Please import ``from __future__ import print_function`` at the very top of the module to enable use of python3 style print functions

Division
--------
Integer division is slightly different in Python3.
``//`` is integer division and ``/`` is floating point division.
For this reason, we use ``division`` from the future module.
Before:

.. code-block:: python

    2 / 3 = 0

After:

.. code-block:: python

    from __future__ import division

    2 / 3 = 1.5
    2 // 3 = 0

Types
-----
The types standard library has changed in Python3.
Please make sure to read the `official documentation <https://docs.python.org/3.3/library/types.html>`_ for the library and adapt accordingly

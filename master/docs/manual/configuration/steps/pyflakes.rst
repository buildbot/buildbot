.. bb:step:: PyFlakes

.. _Step-PyFlakes:

PyFlakes
++++++++

.. py:class:: buildbot.steps.python.PyFlakes

`PyFlakes <https://launchpad.net/pyflakes>`_ is a tool to perform basic static analysis of Python code to look for simple errors, like missing imports and references of undefined names.
It is like a fast and simple form of the C :command:`lint` program.
Other tools (like `pychecker <http://pychecker.sourceforge.net/>`_\) provide more detailed results but take longer to run.

The :bb:step:`PyFlakes` step will run pyflakes and count the various kinds of errors and warnings it detects.

You must supply the command line to be used.
The default is ``make pyflakes``, which assumes you have a top-level :file:`Makefile` with a ``pyflakes`` target.
You might want to use something like ``pyflakes .`` or ``pyflakes src``.

.. code-block:: python

    from buildbot.plugins import steps

    f.addStep(steps.PyFlakes(command=["pyflakes", "src"]))

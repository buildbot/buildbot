.. bb:step:: BuildEPYDoc

.. _Step-BuildEPYDoc:

BuildEPYDoc
+++++++++++

.. py:class:: buildbot.steps.python.BuildEPYDoc

`epydoc <http://epydoc.sourceforge.net/>`_ is a tool for generating
API documentation for Python modules from their docstrings.
It reads all the :file:`.py` files from your source tree, processes the docstrings therein, and creates a large tree of :file:`.html` files (or a single :file:`.pdf` file).

The :bb:step:`BuildEPYDoc` step will run :command:`epydoc` to produce this API documentation, and will count the errors and warnings from its output.

You must supply the command line to be used.
The default is ``make epydocs``, which assumes that your project has a :file:`Makefile` with an `epydocs` target.
You might wish to use something like :samp:`epydoc -o apiref source/{PKGNAME}` instead.
You might also want to add option `--pdf` to generate a PDF file instead of a large tree of HTML files.

The API docs are generated in-place in the build tree (under the workdir, in the subdirectory controlled by the option `-o` argument).
To make them useful, you will probably have to copy them to somewhere they can be read.
For example if you have server with configured nginx web server, you can place generated docs to it's public folder with command like ``rsync -ad apiref/ dev.example.com:~/usr/share/nginx/www/current-apiref/``.
You might instead want to bundle them into a tarball and publish it in the same place where the generated install tarball is placed.

.. code-block:: python

    from buildbot.plugins import steps

    f.addStep(steps.BuildEPYDoc(command=["epydoc", "-o", "apiref", "source/mypkg"]))

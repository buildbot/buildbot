.. bb:step:: Sphinx

.. _Step-Sphinx:

Sphinx
++++++

.. py:class:: buildbot.steps.python.Sphinx

`Sphinx <https://www.sphinx-doc.org/en/master/>`_ is the Python Documentation Generator.
It uses `RestructuredText <http://docutils.sourceforge.net/rst.html>`_ as input format.

The :bb:step:`Sphinx` step will run :program:`sphinx-build` or any other program specified in its ``sphinx`` argument and count the various warnings and error it detects.

.. code-block:: python

    from buildbot.plugins import steps

    f.addStep(steps.Sphinx(sphinx_builddir="_build"))

This step takes the following arguments:

``sphinx_builddir``
   (required) Name of the directory where the documentation will be generated.

``sphinx_sourcedir``
   (optional, defaulting to ``.``), Name the directory where the :file:`conf.py` file will be found

``sphinx_builder``
   (optional) Indicates the builder to use.

``sphinx``
   (optional, defaulting to :program:`sphinx-build`) Indicates the executable to run.

``tags``
   (optional) List of ``tags`` to pass to :program:`sphinx-build`

``defines``
   (optional) Dictionary of defines to overwrite values of the :file:`conf.py` file.

``strict_warnings``
   (optional) Boolean, defaults to False. Treat all warnings as errors.

``mode``
   (optional) String, one of ``full`` or ``incremental`` (the default).
   If set to ``full``, indicates to Sphinx to rebuild everything without re-using the previous build results.

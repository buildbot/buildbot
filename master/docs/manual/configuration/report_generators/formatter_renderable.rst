.. _MessageFormatterRenderable:

MessageFormatterRenderable
++++++++++++++++++++++++++

.. py:currentmodule:: buildbot.reporters.message

This formatter is used to format messages in :ref:`Reportgen-BuildStatusGenerator`.

It renders any renderable using the properties of the build that was passed by the status generator.

The constructor of the class takes the following arguments:

``template``
    A renderable that is used to generate the body of the build report.

``subject``
    A renderable that is used to generate the subject of the build report.

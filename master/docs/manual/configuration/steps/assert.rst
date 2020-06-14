.. bb:step:: Assert

.. _Step-Assert:

Assert
++++++

.. py:class:: buildbot.steps.master.Assert

This build step takes a Renderable or constant passed in as first argument. It will test if the expression evaluates to ``True`` and succeed the step or fail the step otherwise.

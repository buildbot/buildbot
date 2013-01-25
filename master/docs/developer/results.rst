.. _Build-Result-Codes:

Build Result Codes
==================

.. py:module:: buildbot.status.results

Buildbot represents the status of a step, build, or buildset using a set of
numeric constants.  From Python, these constants are available in the module
``buildbot.status.results``, but the values also appear in the database and in
external tools, so the values are fixed.

.. py:data:: SUCCESS

    Value: 0; color: green; a successful run.

.. py:data:: WARNINGS

    Value: 1; color: orange; a successful run, with some warnings.

.. py:data:: FAILURE

    Value: 2; color: red; a failed run, due to problems in the build itself, as
    opposed to a Buildbot misconfiguration or bug.

.. py:data:: SKIPPED

    Value: 3; color: white; a run that was skipped -- usually a step skipped by
    ``doStepIf`` (see :ref:`Buildstep-Common-Parameters`)

.. py:data:: EXCEPTION

    Value: 4; color: purple; a run that failed due to a problem in Buildbot
    itself.

.. py:data:: RETRY

    Value: 4; color: purple; a run that should be retried, usually due to a
    slave disconnection.

.. py:data:: Results

    A dictionary mapping result codes to their lowercase names.

.. py:function:: worst_status(a, b)

    This function takes two status values, and returns the "worst" status of
    the two.  This is used (with exceptions) to aggregate step statuses into
    build statuses, and build statuses into buildset statuses.

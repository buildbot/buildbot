.. _Build-Result-Codes:

Build Result Codes
==================

.. py:module:: buildbot.process.results

Buildbot represents the status of a step, build, or buildset using a set of
numeric constants.  From Python, these constants are available in the module
``buildbot.process.results``, but the values also appear in the database and in
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
    worker disconnection.

.. py:data:: CANCELLED

    Value: 5; color: pink; a run that was cancelled by the user.

.. py:data:: Results

    A dictionary mapping result codes to their lowercase names.

.. py:function:: worst_status(a, b)

    This function takes two status values, and returns the "worst" status of the two.
    This is used to aggregate step statuses into build statuses, and build statuses into buildset statuses.

.. py:function:: computeResultAndTermination(obj, result, previousResult):

    :param obj: an object with the attributes of :py:class:`ResultComputingConfigMixin`
    :param result: the new result
    :param previousResult: the previous aggregated result

    Building on :py:func:`worst_status`, this function determines what the aggreagated overall status is, as well as whether the attempt should be terminated, based on the configuration in ``obj``.

.. py:class:: ResultComputingConfigMixin

    This simple mixin is intended to help implement classes that will use :py:meth:`computeResultAndTermination`.
    The class has, as class attributes, the result computing configuration parameters with default values:

    .. py:attribute:: haltOnFailure
    .. py:attribute:: flunkOnWarnings
    .. py:attribute:: flunkOnFailure
    .. py:attribute:: warnOnWarnings
    .. py:attribute:: warnOnFailure

    The names of these attributes are available in the following attribute:

    .. py:attribute:: resultConfig

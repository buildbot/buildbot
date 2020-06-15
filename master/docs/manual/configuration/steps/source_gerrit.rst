.. bb:step:: Gerrit

.. _Step-Gerrit:

Gerrit
++++++

.. py:class:: buildbot.steps.source.gerrit.Gerrit

:bb:step:`Gerrit` step is exactly like the :bb:step:`Git` step, except that it integrates with :bb:chsrc:`GerritChangeSource`, and will automatically checkout the additional changes.

Gerrit integration can be also triggered using forced build with property named ``gerrit_change`` with values in format ``change_number/patchset_number``.
This property will be translated into a branch name.
This feature allows integrators to build with several pending interdependent changes, which at the moment cannot be described properly in Gerrit, and can only be described by humans.


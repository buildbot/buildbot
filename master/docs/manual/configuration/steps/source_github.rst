.. bb:step:: GitHub

.. _Step-GitHub:

GitHub
++++++

.. py:class:: buildbot.steps.source.github.GitHub

:bb:step:`GitHub` step is exactly like the :bb:step:`Git` step, except that it will ignore the revision sent by the :bb:chsrc:`GitHub` change hook, and rather take the branch if the branch ends with /merge.

This allows to test github pull requests merged directly into the mainline.

GitHub indeed provides ``refs/origin/pull/NNN/merge`` on top of ``refs/origin/pull/NNN/head`` which is a magic ref that always creates a merge commit to the latest version of the mainline (i.e., the target branch for the pull request).

The revision in the GitHub event points to ``/head``, and it's important for the GitHub reporter as this is the revision that will be tagged with a CI status when the build is finished.

If you want to use  :bb:step:`Trigger` to create sub tests and want to have the GitHub reporter still update the original revision, make sure you set ``updateSourceStamp=False`` in the :bb:step:`Trigger` configuration.

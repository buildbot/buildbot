.. bb:step:: GitLab

.. _Step-GitLab:

GitLab
++++++

.. py:class:: buildbot.steps.source.gitlab.GitLab

:bb:step:`GitLab` step is exactly like the :bb:step:`Git` step, except that it uses the source repo and branch sent by the :bb:chsrc:`GitLab` change hook when processing merge requests.

When configuring builders, you can use a ChangeFilter with ``category = "push"``
to select normal commits, and ``category = "merge_request"`` to select merge requests.

See :file:`master/docs/examples/gitlab.cfg` in the Buildbot distribution
for a tutorial example of integrating Buildbot with GitLab.

.. note::

    Your build worker will need access to the source project of the
    changeset, or it won't be able to check out the source.  This means
    authenticating the build worker via ssh credentials in the usual
    way, then granting it access [via a GitLab deploy key
    or GitLab project membership](https://docs.gitlab.com/ee/ssh/).
    This needs to be done not only for the main git repo, but also for
    each fork that wants to be able to submit merge requests against
    the main repo.

.. bb:reporter:: GerritStatusPush

GerritStatusPush
++++++++++++++++

.. py:currentmodule:: buildbot.reporters.status_gerrit

:class:`GerritStatusPush` sends review of the :class:`Change` back to the Gerrit server, optionally also sending a message when a build is started.
GerritStatusPush can send a separate review for each build that completes, or a single review summarizing the results for all of the builds.

.. py:class:: GerritStatusPush(server, username, reviewCB, startCB, port, reviewArg, startArg, summaryCB, summaryArg, identity_file, builders, notify...)

   :param string server: Gerrit SSH server's address to use for push event notifications.
   :param string username: Gerrit SSH server's username.
   :param identity_file: (optional) Gerrit SSH identity file.
   :param int port: (optional) Gerrit SSH server's port (default: 29418)
   :param reviewCB: (optional) Called each time a build finishes. Build properties are available. Can be a deferred.
   :param reviewArg: (optional) Argument passed to the review callback.

                    :: If :py:func:`reviewCB` callback is specified, it must return a message and optionally labels. If no message is specified, nothing will be sent to Gerrit.
                    It should return a dictionary:

                    .. code-block:: python

                        {'message': message,
                         'labels': {label-name: label-score,
                                    ...}
                        }

                    For example:

                    .. literalinclude:: /examples/git_gerrit.cfg
                       :pyobject: gerritReviewCB
                       :language: python

                    Which require an extra import in the config:

                    .. code-block:: python

                       from buildbot.plugins import util

   :param startCB: (optional) Called each time a build is started. Build properties are available. Can be a deferred.
   :param startArg: (optional) Argument passed to the start callback.

                    If :py:func:`startCB` is specified, it must return a message and optionally labels. If no message is specified, nothing will be sent to Gerrit.
                    It should return a dictionary:

                    .. code-block:: python

                        {'message': message,
                         'labels': {label-name: label-score,
                                    ...}
                        }

                    For example:

                    .. literalinclude:: /examples/git_gerrit.cfg
                       :pyobject: gerritStartCB
                       :language: python

   :param summaryCB: (optional) Called each time a buildset finishes. Each build in the buildset has properties available. Can be a deferred.
   :param summaryArg: (optional) Argument passed to the summary callback.

                      If :py:func:`summaryCB` callback is specified, it must return a message and optionally labels. If no message is specified, nothing will be sent to Gerrit.
                      The message and labels should be a summary of all the builds within the buildset.
                      It should return a dictionary:

                      .. code-block:: python

                          {'message': message,
                           'labels': {label-name: label-score,
                                      ...}
                          }

                      For example:

                      .. literalinclude:: /examples/git_gerrit.cfg
                         :pyobject: gerritSummaryCB
                         :language: python

   :param builders: (optional) List of builders to send results for.
                    This method allows to filter results for a specific set of builder.
                    By default, or if builders is None, then no filtering is performed.
   :param notify: (optional) Control who gets notified by Gerrit once the status is posted.
                  The possible values for `notify` can be found in your version of the
                  Gerrit documentation for the `gerrit review` command.

   :param wantSteps: (optional, defaults to False) Extends the given ``build`` object with information about steps of the build.
                     Use it only when necessary as this increases the overhead in term of CPU and memory on the master.

   :param wantLogs: (optional, default to False) Extends the steps of the given ``build`` object with the full logs of the build.
                    This requires ``wantSteps`` to be True.
                    Use it only when mandatory as this increases the overhead in term of CPU and memory on the master greatly.

.. note::

   By default, a single summary review is sent; that is, a default :py:func:`summaryCB` is provided, but no :py:func:`reviewCB` or :py:func:`startCB`.

.. note::

   If :py:func:`reviewCB` or :py:func:`summaryCB` do not return any labels, only a message will be pushed to the Gerrit server.

.. seealso::

   :src:`master/docs/examples/git_gerrit.cfg` and :src:`master/docs/examples/repo_gerrit.cfg` in the Buildbot distribution provide a full example setup of Git+Gerrit or Repo+Gerrit of :bb:reporter:`GerritStatusPush`.

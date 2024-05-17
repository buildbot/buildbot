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
   :param notify: (optional) Control who gets notified by Gerrit once the status is posted.
                  The possible values for `notify` can be found in your version of the
                  Gerrit documentation for the `gerrit review` command.


.. note::

   By default, a single summary review is sent; that is, a default :py:func:`summaryCB` is provided, but no :py:func:`reviewCB` or :py:func:`startCB`.

.. note::

   If :py:func:`reviewCB` or :py:func:`summaryCB` do not return any labels, only a message will be pushed to the Gerrit server.

.. seealso::

   :src:`master/docs/examples/git_gerrit.cfg` and :src:`master/docs/examples/repo_gerrit.cfg` in the Buildbot distribution provide a full example setup of Git+Gerrit or Repo+Gerrit of :bb:reporter:`GerritStatusPush`.

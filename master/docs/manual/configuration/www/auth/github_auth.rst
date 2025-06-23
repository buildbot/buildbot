.. _WWW-Auth-GitHubAuth:

GitHubAuth
==========

.. py:class:: buildbot.www.oauth2.GitHubAuth(clientId, clientSecret)

    :param clientId: The client ID of your buildbot application
    :param clientSecret: The client secret of your buildbot application
    :param serverURL: The server URL if this is a GitHub Enterprise server
    :param apiVersion: The GitHub API version to use. One of ``3`` or ``4``
                       (V3/REST or V4/GraphQL). Defaults to 3.
    :param getTeamsMembership: When ``True`` fetch all team memberships for each of the
                               organizations the user belongs to. The teams will be included in the
                               user's groups as ``org-name/team-name``.
    :param debug: When ``True`` and using ``apiVersion=4`` show some additional log calls with the
                  GraphQL queries and responses for debugging purposes.
    :param boolean ssl_verify: If False disables SSL certificate verification

    This class implements an authentication with GitHub_ single sign-on.
    It functions almost identically to the :py:class:`~buildbot.www.oauth2.GoogleAuth` class.

    Register your Buildbot instance with the ``BUILDBOT_URL/auth/login`` url as the allowed redirect URI.

    The user's email-address (for e.g. authorization) is set to the "primary" address set by the user in GitHub.
    When using group-based authorization, the user's groups are equal to the names of the GitHub organizations the user
    is a member of.

    Example:

    .. code-block:: python

        from buildbot.plugins import util
        c['www'] = {
            # ...
            'auth': util.GitHubAuth("clientid", "clientsecret"),
        }

    Example for Enterprise GitHub:

    .. code-block:: python

        from buildbot.plugins import util
        c['www'] = {
            # ...
            'auth': util.GitHubAuth("clientid", "clientsecret",
                                    "https://git.corp.mycompany.com"),
        }

    An example on fetching team membership could be:

    .. code-block:: python

        from buildbot.plugins import util
        c['www'] = {
            # ...
            'auth': util.GitHubAuth("clientid", "clientsecret", apiVersion=4,
                                    getTeamsMembership=True),
            'authz': util.Authz(
                allowRules=[
                  util.AnyControlEndpointMatcher(role="core-developers"),
                ],
                roleMatchers=[
                  util.RolesFromGroups(groupPrefix='buildbot/')
                ]
              )
        }

  If the ``buildbot`` organization had two teams, for example, 'core-developers' and 'contributors',
  with the above example, any user belonging to those teams would be granted the roles matching those
  team names.

  In order to use this module, you need to install the Python ``requests`` module:

  .. code-block:: bash

          pip install requests

.. _GitHub: https://developer.github.com/apps/building-oauth-apps/authorizing-oauth-apps/#web-application-flow

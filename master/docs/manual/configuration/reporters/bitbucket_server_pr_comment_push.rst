.. bb:reporter:: BitbucketServerPRCommentPush

BitbucketServerPRCommentPush
++++++++++++++++++++++++++++

.. py:currentmodule:: buildbot.reporters.bitbucketserver

.. code-block:: python

    from buildbot.plugins import reporters

    ss = reporters.BitbucketServerPRCommentPush('https://bitbucket-server.example.com:8080/',
                                                'bitbucket_server__username',
                                                'secret_password')
    c['services'].append(ss)


:class:`BitbucketServerPRCommentPush` publishes a comment on a PR using `Bitbucket Server REST API <https://developer.atlassian.com/static/rest/bitbucket-server/5.0.1/bitbucket-rest.html#idm45993793481168>`_.


.. py:class:: BitbucketServerPRCommentPush(base_url, user, password, verbose=False, debug=None, verify=None, mode=('failing', 'passing', 'warnings'), tags=None, generators=None)

The following parameters are accepted by this reporter:

``base_url``
    (string)
    The base url of the Bitbucket server host.

``user``
    (string)
    The Bitbucket server user to post as. (can be a :ref:`Secret`)

``password``
    (string)
    The Bitbucket server user's password. (can be a :ref:`Secret`)

``generators``
    (list)
    A list of instances of ``IReportGenerator`` which defines the conditions of when the messages will be sent and contents of them.
    See :ref:`Report-Generators` for more information.

``verbose``
    (boolean, defaults to ``False``)
    If ``True``, logs a message for each successful status push.

``debug``
    (boolean, defaults to ``False``)
    If ``True``, logs every requests and their response

``verify``
    (boolean, defaults to ``None``)
    If ``False``, disables SSL verification for the case you use temporary self signed certificates.
    Default enables SSL verification.

.. Note::
    This reporter depends on the Bitbucket server hook to get the pull request url.

.. bb:reporter:: ZulipStatusPush

ZulipStatusPush
+++++++++++++++

.. py:currentmodule:: buildbot.reporters.zulip

.. code-block:: python

    from buildbot.plugins import reporters

    zs = reporters.ZulipStatusPush(endpoint='your-organization@zulipchat.com',
                                   token='private-token', stream='stream_to_post_in')
    c['services'].append(zs)

:class:`ZulipStatusPush` sends build status using `The Zulip API <https://zulipchat.com/api/>`_.
The build status is sent to a user as a private message or in a stream in Zulip.

.. py:class:: ZulipStatusPush(endpoint, token, stream=None)

    :param string endpoint: URL of your Zulip server
    :param string token: Private API token
    :param string stream: The stream in which the build status is to be sent. Defaults to None


.. note::

   A private message is sent if stream is set to None.

Json object spec
~~~~~~~~~~~~~~~~

The json object sent contains the following build status values.

.. code-block:: json

    {
        "event": "new/finished",
        "buildid": "<buildid>",
        "buildername": "<builder name>",
        "url": "<URL to the build>",
        "project": "name of the project",
        "timestamp": "<timestamp at start/finish>"
    }

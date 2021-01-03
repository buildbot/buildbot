.. _Pushover: https://pushover.net/

.. bb:reporter:: PushoverNotifier

PushoverNotifier
++++++++++++++++

.. py:currentmodule:: buildbot.reporters.pushover

.. py:class:: buildbot.reporters.pushover.PushoverNotifier

Apart of sending mail, Buildbot can send Pushover_ notifications. It can be used by administrators to receive an instant message to an iPhone or an Android device if a build fails. The :class:`PushoverNotifier` reporter is used to accomplish this. Its configuration is very similar to the mail notifications, however—due to the notification size constrains—the logs and patches cannot be attached.

To use this reporter, you need to generate an application on the Pushover website https://pushover.net/apps/ and provide your user key and the API token.

The following simple example will send a Pushover notification upon the completion of each build.
The notification contains a description of the :class:`Build`, its results, and URLs where more information can be obtained. The ``user_key`` and ``api_token`` values should be replaced with proper ones obtained from the Pushover website for your application.

.. code-block:: python

    from buildbot.plugins import reporters
    pn = reporters.PushoverNotifier(user_key="1234", api_token='abcd')
    c['services'].append(pn)

The following parameters are accepted by this class:

``generators``
    (list)
    A list of instances of ``IReportGenerator`` which defines the conditions of when the messages will be sent and contents of them.
    See :ref:`Report-Generators` for more information.

``user_key``
    The user key from the Pushover website. It is used to identify the notification recipient.
    Can be a :ref:`Secret`.

``api_token``
    API token for a custom application from the Pushover website.
    Can be a :ref:`Secret`.

``priorities``
    Dictionary of Pushover notification priorities. The keys of the dictionary can be ``change``, ``failing``, ``passing``, ``warnings``, ``exception`` and are equivalent to the ``mode`` strings. The values are integers between -2...2, specifying notification priority. In case a mode is missing from this dictionary, the default value of 0 is used.

``otherParams``
    Other parameters send to Pushover API. Check https://pushover.net/api/ for their list.

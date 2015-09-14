.. _Upgrading To Nine:

Upgrading to Nine
=================

Upgrading a Buildbot instance from 0.8.x to 0.9.x may require a number of changes to the master configuration.
Those changes are summarized here.
If you are starting fresh with 0.9.0 or later, you can safely skip this section.

Config File Syntax
------------------

In preparation for compatibility with Python 3, Buildbot coniguration files no longer allow the print statement:

.. code-block:: python

    print "foo"

To fix, simply enclose the print arguments in parentheses:

.. code-block:: python

    print("foo")

Plugins
-------

Although plugin support was available in 0.8.12, its use is now highly recommended.
Instead of importing modules directly in ``master.cfg``, import the plugin kind from ``buildbot.plugins``:

.. code-block:: python

    from buildbot.plugins import steps

Then access the plugin itself as an attribute:

.. code-block:: python

    steps.SetProperty(..)

See :ref:`Plugins` for more information.

Web Status
----------

The most prominent change is that the existing ``WebStatus`` class is now gone, replaced by the new ``www`` functionality.

Thus an ``html.WebStatus`` entry in ``c['status']`` should be removed and replaced with configuration in ``c['www']```.
For example, replace:

.. code-block:: python

    from buildbot.status import html
    c['status'].append(html.WebStatus(http_port=8010, allowForce=True)

with:

.. code-block:: python

    c['www'] = dict(port=8020,
                    plugins=dict(waterfall_view={},
                    console_view={}))

See :bb:cfg:`www` for more information.

Status Reporters
----------------

In fact, the whole ``c['status']`` configuration parameter is gone.
Many of the status listeners used in the status hierarchy in 0.8.x have been replaced with "reporters" that are availabale as buildbot plugins.
However, note that not all status listeners have yet been ported.
See the release notes for details.

The available reporters as of 0.9.0 are

* :bb:reporter:`MailNotifier`

* :bb:reporter:`IRC`

* :bb:reporter:`StatusPush`

* :bb:reporter:`HttpStatusPush`

* :bb:reporter:`GerritStatusPush`

* :bb:reporter:`GitHubStatus`

See the reporter index for the full, current list.

A few notes on changes to the configuration of these reporters:

* :bb:reporter:`MailNotifier` argument ``messageFormatter`` should now be a `~buildbot.status.message.MessageFormatter`, due to removal of data api, custom message formaters need to be rewritten.

* :bb:reporter:`MailNotifier` argument ``previousBuildGetter`` is not supported anymore

* :bb:reporter:`MailNotifier` no longer forces SSL 3.0 when ``useTls`` is true.

* :bb:reporter:`GerritStatusPush` callbacks slightly changed signature, and include a master reference instead of a status reference.

* :bb:reporter:`GitHubStatus` now accepts a ``context`` parameter to be passed to the GitHub Status API.

Steps
-----

Buildbot-0.8.9 introduced "new-style steps", with an asynchronous ``run`` method.
In the remaining 0.8.x releases, use of new-style and old-style steps were supported side-by-side.
In 0.9.x, old-style steps are emulated using a collection of hacks to allow asynchronous calls to be called from synchronous code.
This emulation is imperfect, and you are strongly encouraged to rewrite any custom steps as new-style steps.

Identifiers
-----------

Many strings in Buildbot must now be identifiers.
Identifiers are designed to fit easily and unambiguously into URLs, AMQP routes, and the like.
An "identifier" is a nonempty unicode string of limited length, containing only ASCII alphanumeric characters along with ``-`` (dash) and ``_`` (underscore), and not beginning with a digit

Unfortunately, many existing names do not fit this pattern.

The following fields are identifiers:

* buildslave name (50-character)
* builder name (20-character)
* step name (50-character)

Build History
-------------

There is no support for importing build history from 0.8.x (where the history was stored on-disk in pickle files) into 0.9.x (where it is stored in the database).

More Information
----------------

For minor changes not mentioned here, consult the release notes for the versions over which you are upgrading.

Buildbot-0.9.0 represents several years' work, and as such we may have missed potential migration issues.
To find the latest "gotchas" and share with other users, see http://trac.buildbot.net/wiki/XXX XXX


.. _ConsoleView:

Console View
============

Console view shows the whole Buildbot activity arranged by changes as discovered by :ref:`Change-Sources` vertically and builders horizontally.
If a builder has no build in the current time range, it will not be displayed.
If no change is available for a build, then it will generate a fake change according to the ``got_revision`` property.

Console view will also group the builders by tags.
When there are several tags defined per builders, it will first group the builders by the tag that is defined for most builders.
Then given those builders, it will group them again in another tag cluster.
In order to keep the UI usable, you have to keep your tags short!

    .. code-block:: bash

        pip install buildbot-console-view

    .. code-block:: python

        c['www'] = {
            'plugins': {'console_view': True}
        }


.. note::

    Nine's Console View is the equivalent of Buildbot Eight's Console and tgrid views.
    Unlike Waterfall, we think it is now feature equivalent and even better, with its live update capabilities.
    Please submit an issue if you think there is an issue displaying your data, with screen shots of what happen and suggestion on what to improve.

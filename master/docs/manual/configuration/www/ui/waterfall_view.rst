
.. _WaterfallView:

Waterfall View
==============

Waterfall shows the whole Buildbot activity in a vertical time line.
Builds are represented with boxes whose height vary according to their duration.
Builds are sorted by builders in the horizontal axes, which allows you to see how builders are scheduled together.

    .. code-block:: bash

        pip install buildbot-waterfall-view

    .. code-block:: python

        c['www'] = {
            'plugins': {'waterfall_view': True}
        }


.. note::

    Waterfall is the emblematic view of Buildbot Eight.
    It allowed to see the whole Buildbot activity very quickly.
    Waterfall however had big scalability issues, and larger installs had to disable the page in order to avoid tens of seconds master hang because of a big waterfall page rendering.
    The whole Buildbot Eight internal status API has been tailored in order to make Waterfall possible.
    This is not the case anymore with Buildbot Nine, which has a more generic and scalable :ref:`Data_API` and :ref:`REST_API`.
    This is the reason why Waterfall does not display the steps details anymore.
    However nothing is impossible.
    We could make a specific REST api available to generate all the data needed for waterfall on the server.
    Please step-in if you want to help improve the Waterfall view.

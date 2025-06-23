
.. _Badges:

Badges
======

Buildbot badges plugin produces an image in SVG or PNG format with information about the last build for the given builder name.
PNG generation is based on the CAIRO_ SVG engine, it requires a bit more CPU to generate.


   .. code-block:: bash

      pip install buildbot-badges

   .. code-block:: python

      c['www'] = {
          'plugins': {'badges': {}}
      }

You can the access your builder's badges using urls like ``http://<buildbotURL>/plugins/badges/<buildername>.svg``.
The default templates are very much configurable via the following options:

.. code-block:: python

    {
        "left_pad"  : 5,
        "left_text": "Build Status",  # text on the left part of the image
        "left_color": "#555",  # color of the left part of the image
        "right_pad" : 5,
        "border_radius" : 5, # Border Radius on flat and plastic badges
        # style of the template availables are "flat", "flat-square", "plastic"
        "style": "plastic",
        "template_name": "{style}.svg.j2",  # name of the template
        "font_face": "DejaVu Sans",
        "font_size": 11,
        "color_scheme": {  # color to be used for right part of the image
            "exception": "#007ec6",  # blue
            "failure": "#e05d44",    # red
            "retry": "#007ec6",      # blue
            "running": "#007ec6",    # blue
            "skipped": "a4a61d",     # yellowgreen
            "success": "#4c1",       # brightgreen
            "unknown": "#9f9f9f",    # lightgrey
            "warnings": "#dfb317"    # yellow
        }
    }

Those options can be configured either using the plugin configuration:

.. code-block:: python

      c['www'] = {
          'plugins': {'badges': {"left_color": "#222"}}
      }

or via the URL arguments like ``http://<buildbotURL>/plugins/badges/<buildername>.svg?left_color=222``.
Custom templates can also be specified in a ``template`` directory nearby the ``master.cfg``.

The badgeio template
^^^^^^^^^^^^^^^^^^^^

A badges template was developed to standardize upon a consistent "look and feel" across the usage of
multiple CI/CD solutions, e.g.: use of Buildbot, Codecov.io, and Travis-CI. An example is shown below.

.. image:: ../../../../_images/badges-badgeio.png

To ensure the correct "look and feel", the following Buildbot configuration is needed:

.. code-block:: python

    c['www'] = {
        'plugins': {
            'badges': {
                "left_pad": 0,
                "right_pad": 0,
                "border_radius": 3,
                "style": "badgeio"
            }
        }
    }

.. note::

    It is highly recommended to use only with SVG.

.. _CAIRO: https://www.cairographics.org/

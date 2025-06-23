
.. _GridView:

Grid View
=========

Grid view shows the whole Buildbot activity arranged by builders vertically and changes horizontally.
It is equivalent to Buildbot Eight's grid view.

By default, changes on all branches are displayed but only one branch may be filtered by the user.
Builders can also be filtered by tags.
This feature is similar to the one in the builder list.

   .. code-block:: bash

      pip install buildbot-grid-view

   .. code-block:: python

      c['www'] = {
          'plugins': {'grid_view': True}
      }

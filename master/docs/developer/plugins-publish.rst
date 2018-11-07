===============================
How to package Buildbot plugins
===============================

If you customized an existing component (see :doc:`../manual/customization`) or created a new component that you believe might be useful for others, you have two options:

* submit the change to the Buildbot main tree, however you need to adhere to certain requirements (see :doc:`style`)
* prepare a Python package that contains the functionality you created

Here we cover the second option.

Package the source
==================

To begin with, you must package your changes.
If you do not know what a Python package is, these two tutorials will get you going:

* `Python Packaging User Guide <https://packaging.python.org/en/latest/>`__
* `The Hitchhiker’s Guide to Packaging <https://the-hitchhikers-guide-to-packaging.readthedocs.org/en/latest/>`__

The former is more recent and, while it addresses everything that you need to know about Python packages, is still work in progress.
The latter is a bit dated, though it was the most complete guide for quite some time available for Python developers looking to package their software.

You may also want to check the `sample project <https://github.com/pypa/sampleproject>`_, which exemplifies the best Python packaging practices.

Making the plugin package
=========================

Buildbot supports several kinds of pluggable components:

* ``worker``
* ``changes``
* ``schedulers``
* ``steps``
* ``status``
* ``util``

(these are described in :doc:`../manual/plugins`), and

* ``www``

which is described in :doc:`web server configuration <../manual/configuration/www>`.

Once you have your component packaged, it's quite straightforward: you just need to add a few lines to the ``entry_points`` parameter of your call of ``setup`` function in :file:`setup.py` file:

.. code-block:: python

    setup(
        ...
        entry_points = {
            ...,
            'buildbot.kind': [
                'PluginName = PluginModule:PluginClass'
            ]
        },
        ...
    )

(You might have seen different ways to specify the value for ``entry_points``, however they all do the same thing.
Full description of possible ways is available in `setuptools documentation <https://setuptools.readthedocs.io/en/latest/setuptools.html#dynamic-discovery-of-services-and-plugins>`_.)

After the :src:`setup.py <master/setup.py>` file is updated, you can build and install it:

.. code-block:: none

    $ python setup.py build
    $ sudo python setup.py install

(depending on your particular setup, you might not need to use :command:`sudo`).

After that the plugin should be available for Buildbot and you can use it in your :file:`master.cfg` as:

.. code-block:: python

    from buildbot.kind import PluginName

    ... PluginName ...

Publish the package
===================

This is the last step before the plugin is available to others.

Once again, there is a number of options available for you:

* just put a link to your version control system
* prepare a source tarball with the plugin (``python setup.py sdist``)
* or publish it on `PyPI <https://pypi.python.org>`_

The last option is probably the best one since it will make your plugin available pretty much to all Python developers.

Once you have published the package, please send a link to `buildbot-devel <mailto:buildbot-devel@lists.sourceforge.net>`_ mailing list, so we can include a link to your plugin to :doc:`../manual/plugins`.

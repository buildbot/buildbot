.. _Custom-Build-Classes:

Custom Build Classes
--------------------

The standard :class:`BuildFactory` object creates :class:`Build` objects by default. These Builds
will each execute a collection of :class:`BuildStep`\s in a fixed sequence. Each step can affect
the results of the build, but in general there is little intelligence to tie the different steps
together.

By setting the factory's ``buildClass`` attribute to a different class, you can instantiate a
different build class. This might be useful, for example, to create a build class that dynamically
determines which steps to run. The skeleton of such a project would look like:

.. code-block:: python

    class DynamicBuild(Build):
        # override some methods
        ...

    f = factory.BuildFactory()
    f.buildClass = DynamicBuild
    f.addStep(...)

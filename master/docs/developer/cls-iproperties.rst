.. index:: single: Properties; IProperties

IProperties
===========

.. class:: buildbot.interfaces.IProperties::

   Providers of this interface allow get and set access to a build's properties.

   .. method:: getProperty(propname, default=None)

      Get a named property, returning the default value if the property is not found.

   .. method:: hasProperty(propname)

      Determine whether the named property exists.

   .. method:: setProperty(propname, value, source)

      Set a property's value, also specifying the source for this value.

   .. method:: getProperties()

      Get a :class:`buildbot.process.properties.Properties` instance.
      The interface of this class is not finalized; where possible, use the other ``IProperties`` methods.

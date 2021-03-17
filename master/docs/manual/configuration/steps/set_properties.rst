.. bb:step:: SetProperties

.. _Step-SetProperties:

SetProperties
+++++++++++++

.. py:class:: buildbot.steps.master.SetProperties

:bb:step:`SetProperties` takes a dictionary to be turned into build properties.

It is similar to :bb:step:`SetProperty`, and meant to be used with a :ref:`renderer` function or a dictionary of :ref:`Interpolate` objects which allows the value to be built from other property values:

.. code-block:: python

    """Example borrowed from Julia's master.cfg
       https://github.com/staticfloat/julia-buildbot (MIT)"""
    from buildbot.plugins import *

    @util.renderer
    def compute_artifact_filename(props):
        # Get the output of the `make print-BINARYDIST_FILENAME` step
        reported_filename = props.getProperty('artifact_filename')

        # First, see if we got a BINARYDIST_FILENAME output
        if reported_filename[:26] == "BINARYDIST_FILENAME=":
            local_filename = util.Interpolate(reported_filename[26:].strip() +
                                              "%(prop:os_pkg_ext)s")
        else:
            # If not, use non-sf/consistent_distnames naming
            if is_mac(props):
                template = \
                    "path/to/Julia-%(prop:version)s-%(prop:shortcommit)s.%(prop:os_pkg_ext)s"
            elif is_winnt(props):
                template = \
                    "julia-%(prop:version)s-%(prop:tar_arch)s.%(prop:os_pkg_ext)s"
            else:
                template = \
                    "julia-%(prop:shortcommit)s-Linux-%(prop:tar_arch)s.%(prop:os_pkg_ext)s"

            local_filename = util.Interpolate(template)

        # upload_filename always follows sf/consistent_distname rules
        upload_filename = util.Interpolate(
            "julia-%(prop:shortcommit)s-%(prop:os_name)s%(prop:bits)s.%(prop:os_pkg_ext)s")

        return {
            "local_filename": local_filename
            "upload_filename": upload_filename
        }

    f1.addStep(steps.SetProperties(properties=compute_artifact_filename))

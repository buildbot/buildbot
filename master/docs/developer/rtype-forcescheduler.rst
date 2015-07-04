ForceScheduler
==============

.. bb:rtype:: forcescheduler

    :attr string name: name of this scheduler
    :attr string name: label of this scheduler to be displayed in the ui
    :attr list buildernames: names of the builders that this scheduler can trigger
    :attr jsonObject all_fields: description of the fields that will be displayed in the UI

    A forcescheduler initiates builds, via a formular in the web UI.
    At the moment, forceschedulers must be defined on all the masters where a web ui is configured. A particular forcescheduler runs on the master where the web request was sent.

    .. bb:rpath:: /forceschedulers

        This path selects all forceschedulers.

        This endpoint has a control method with the following action:

        * force:

            create a buildrequest with this forcescheduler. It takes as parameters:

                - owner: the username that requested this build.
                - builderid: the builderid of the builder to force if builderNames is not specified
                - builderNames: the buildername of the builder to force
                - other params: other named params are the configured parameters of the forcescheduler

    .. bb:rpath:: /forceschedulers/:schedulername

        :pathkey string schedulername: the name of the scheduler

        This path selects a specific scheduler, identified by name.


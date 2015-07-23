Authorization
=============

Buildbot authorization is designed to address the following requirements

    - Most of the configuration is only data: We avoid to require user to write callbacks for most of the use cases. This to allow to load the config from yaml or json and eventually do a UI for authorization config.
    - Separation of concerns:

        * Mapping users to roles
        * Mapping roles to REST endpoints.

    - Configuration should not need hardcoding endpoint paths.
    - Easy to extend

Use cases
---------

- Members of admin group should have access to all resources and actions
- developers can run the "try" builders
- Integrators can run the "merge" builders
- Release team can run the "release" builders
- There are separate teams for different branches or projects, but the roles are identic
- Owners of builds can stop builds or buildrequests
- Secret branch's builds are hidden from people except explicitly authorized


class Route extends Config
    constructor: ($urlRouterProvider, glMenuServiceProvider, $locationProvider, $qProvider, $compileProvider, config) ->
        # angularjs 1.6 sets ! as default prefix, but this would break all our URLs!
        $locationProvider.hashPrefix('')
        $compileProvider.preAssignBindingsEnabled(true)
        # workaround https://github.com/angular-ui/ui-router/issues/2889
        $qProvider.errorOnUnhandledRejections(false)
        $urlRouterProvider.otherwise('/')
        # the app title needs to be < 18 chars else the UI looks bad
        # we try to find best option
        if config.title?
            apptitle = "Buildbot: "+ config.title
            if apptitle.length > 18
                apptitle = config.title
            if apptitle.length > 18
                apptitle = "Buildbot"
        else
            apptitle = "Buildbot"
        glMenuServiceProvider.setAppTitle(apptitle)
        # all states config are in the modules

class Route extends Config
    constructor: ($urlRouterProvider, glMenuServiceProvider, config) ->
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

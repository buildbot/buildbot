class Route extends Config
    constructor: ($urlRouterProvider, glMenuServiceProvider, $wampProvider, config) ->
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
        if config.wamp?
            $wampProvider.init
                url: config.wamp.router_url,
                realm: config.wamp.realm
        else
            $wampProvider.init
                url: "ws://foo.com",

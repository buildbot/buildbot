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
        url = config.buildbotURL
        if url?
            url = url.replace("http://", "ws://").replace("https://", "wss://") + "ws"
            $wampProvider.init
                url: url,
                realm: 'buildbot'

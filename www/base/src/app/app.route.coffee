class Route extends Config
    constructor: ($urlRouterProvider, glMenuServiceProvider) ->
        $urlRouterProvider.otherwise('/')
        glMenuServiceProvider.setAppTitle("Buildbot")
        # all states config are in the modules

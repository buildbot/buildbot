class Route extends Config
    constructor: ($urlRouterProvider) ->
        $urlRouterProvider.otherwise('/')
        # all states config are in the modules
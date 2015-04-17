class Route extends Config
    constructor: ($urlRouterProvider) ->
        $urlRouterProvider.otherwise('/')

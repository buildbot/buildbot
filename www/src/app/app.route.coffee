
angular.module('app').config [ '$stateProvider', '$urlRouterProvider',
    ($stateProvider, $urlRouterProvider) ->

        $urlRouterProvider.otherwise('/')

        # by convention, in this module the key of the mapping
        # is the name of the template and of the controller
        # If the route has a caption, it is linked in the top menu
        # The route is configured in $routeProvider
        default_routes =
        #    lastbuilds:
        #        caption: 'Last Builds'
        #        url: '/lastbuilds'
        #    users:
        #        caption: 'Users'
        #        url: '/users'
        #    admin:
        #        caption: 'Admin'
        #        url: '/admin'
            user:
                url: '/users/:user'
                tabid: 'users'
            editconf:
                url: '/admin/:conffile'
                tabid: 'admin'

        for id, cfg of default_routes
            cfg.tabid ?= id
            cfg.tabhash = "##{id}"
            state =
                controller: cfg.controller ? "#{id}Controller"
                templateUrl: cfg.templateUrl ? "views/#{id}.html"
                name: id
                url: cfg.url
                data: cfg

            $stateProvider.state(state)
]
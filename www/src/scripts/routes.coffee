angular.module('app').config ['$routeProvider', ($routeProvider) ->
        # by convention, the key of the first mapping
        # is the name of the template and of the controller
        # If the route has a caption, it is linked in the top menu
        # The route is configured in $routeProvider
        # $scope is not available at this time.
        # @hack Need to find a better 'angularonic' way of passing the info to topmenu
        # than global variable
        window.route_config =
                home:
                    caption:"Home"
                    route:"/"
                overview:
                    caption:"Overview"
                    route:"/overview"
                builders:
                    caption:"Builders"
                    route:"/builders"
                lastbuilds:
                    caption:"Last Builds"
                    route:"/lastbuilds"
                changes:
                    caption:"Last Changes"
                    route:"/changes"
                buildslaves:
                    caption:"Build Slaves"
                    route:"/buildslaves"
                buildmasters:
                    caption:"Build Masters"
                    route:"/buildmasters"
                users:
                    caption:"Users"
                    route:"/users"
                admin:
                    caption:"Admin"
                    route:"/admin"


                builder:
                    route:"/builders/:builder"
                    tabid:"builders"
                build:
                    route:"/builders/:builder/:build"
                    tabid:"builders"
                step:
                    route:"/builders/:builder/:build/steps/:step"
                    tabid:"builders"
                log:
                    route:"/builders/:builder/:build/steps/:step/logs/:log"
                    tabid:"builders"

                buildslave:
                    route:"/buildslaves/:buildslave"
                    tabid:"buildslaves"
                buildmaster:
                    route:"/buildmasters/:buildmaster"
                    tabid:"buildmasters"
                user:
                    route:"/users/:user"
                    tabid:"users"

                editconf:
                    route:"/admin/:conffile"
                    tabid:"admin"

        for id, cfg of window.route_config
            cfg.tabid?=id
            cfg.tabhash="##{id}"
            $routeProvider
            .when cfg.route,
                    controller: "#{id}Controller"
                    reloadOnSearch: true
                    templateUrl: "views/#{id}.html"
                    resolve:
                            changeTab: ['$rootScope', ($rootScope) ->
                                $rootScope.$broadcast 'changeTab#'+cfg.tabid
                            ]
        $routeProvider.otherwise redirectTo: '/'
]
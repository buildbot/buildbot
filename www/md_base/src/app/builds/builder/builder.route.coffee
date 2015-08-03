class State extends Config
    constructor: ($urlRouterProvider, $stateProvider) ->

        # Name of the state
        name = 'builds.builder'

        # Register new state
        $stateProvider.state
            controller: "builderController"
            controllerAs: 'builder'
            templateUrl: "views/#{name}.html"
            name: name
            url: '/builder/:builderid'
            data:
                title: 'Builder'

        # Dummy state for navigating among tabs
        $stateProvider.state
            name: 'builds.builder.buildstab'
            url: '/buildstab'
            templateUrl: "views/#{name}.buildstab.html"
            controller: [
                '$scope',
                ($scope) ->
                    $scope.builder.selectTab('buildstab')
            ]

        $stateProvider.state
            name: 'builds.builder.infotab'
            url: '/infotab'
            templateUrl: "views/#{name}.infotab.html"
            controller: [
                '$scope',
                ($scope) ->
                    $scope.builder.selectTab('infotab')
            ]

        $stateProvider.state
            name: 'builds.builder.buildtab'
            url: '/buildtab/{number:int}'
            templateUrl: "views/#{name}.buildtab.html"
            controller: 'buildTabController'
            controllerAs: 'buildtab'

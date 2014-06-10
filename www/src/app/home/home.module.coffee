name = 'buildbot.home'
dependencies = [
    'buildbot.common'
    'ui.router'
]

# Register new module
angular.module name, dependencies
angular.module('app').requires.push(name)

angular.module('buildbot.home').config ['$stateProvider',
    ($stateProvider) ->

        # Name of the state
        name = 'home'

        # Configuration
        cfg =
            caption: 'Home'

        # Register new state
        $stateProvider.state
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/'
            data: cfg

]

angular.module('buildbot.home').controller 'homeController',
['$scope', 'recentStorage'
    ($scope, recentStorage) ->
        $scope.recent = {}
        recentStorage.getAll().then (e) ->
            $scope.recent.recent_builders = e.recent_builders
            $scope.recent.recent_builds = e.recent_builds
        $scope.clear = ->
            recentStorage.clearAll().then ->
                recentStorage.getAll().then (e) ->
                    $scope.recent.recent_builders = e.recent_builders
                    $scope.recent.recent_builds = e.recent_builds
]

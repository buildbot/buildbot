name = 'buildbot.buildslaves'
dependencies = [
    'ui.router'
    'buildbot.common'
]

# Register new module
m = angular.module name, dependencies
angular.module('app').requires.push(name)

m.config ['$stateProvider',
    ($stateProvider) ->

        # Name of the state
        name = 'buildslaves'

        # Configuration
        cfg =
            tabid: name
            tabhash: "##{name}"
            caption: 'Build Slaves'

        # Register new state
        $stateProvider.state
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/buildslaves'
            data: cfg
]

m.controller 'buildslavesController',
['$scope', 'buildbotService',
    ($scope, buildbotService) ->

        buildbotService.all('buildslaves').bind($scope)

]

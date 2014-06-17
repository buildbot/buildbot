name = 'buildbot.masters'
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
        name = 'masters'

        # Configuration
        cfg =
            tabid: name
            tabhash: "##{name}"
            caption: 'Build Masters'

        # Register new state
        state =
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/masters'
            data: cfg

        $stateProvider.state(state)
]

m.controller 'mastersController',
['$scope', 'buildbotService',
    ($scope, buildbotService) ->

        buildbotService.all('masters').bind($scope)

]

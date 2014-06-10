name = 'buildbot.changes'
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
        name = 'changes'

        # Configuration
        cfg =
            tabid: name
            tabhash: "##{name}"
            caption: 'Last Changes'

        # Register new state
        state =
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/changes'
            data: cfg

        $stateProvider.state(state)
]

m.controller 'changesController',
['$log', '$scope', 'buildbotService'
    ($log, $scope, buildbotService) ->
        buildbotService.all('changes').bind($scope)
]

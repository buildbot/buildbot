name = 'buildbot.schedulers'
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
        name = 'schedulers'

        # Configuration
        cfg =
            tabid: name
            tabhash: "##{name}"
            caption: 'Schedulers'

        # Register new state
        $stateProvider.state
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/schedulers'
            data: cfg

]

m.controller 'schedulersController',
['$log', '$scope', '$location', 'buildbotService',
    ($log, $scope, $location, buildbotService) ->
        buildbotService.all('schedulers').bind($scope)
 ]

name = 'buildbot.builders'
dependencies = [
    'ui.router'
    'ui.bootstrap'
    'RecursionHelper'
    'buildbot.common'
]

# Register new module
m = angular.module name, dependencies
angular.module('app').requires.push(name)

m.config ['$stateProvider',
    ($stateProvider) ->

        # Name of the state
        name = 'builders'

        # Configuration
        # Configuration
        cfg =
            tabid: name
            tabhash: "##{name}"
            caption: 'Builders'

        # Register new state
        state =
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/builders'
            data: cfg

        $stateProvider.state(state)
]

m.controller 'buildersController',
['$scope', 'buildbotService','resultsService',
    ($scope, buildbotService, resultsService) ->
        # make resultsService utilities available in the template
        _.mixin($scope, resultsService)

        buildbotService.all('builders').bind $scope,
            onchild: (builder) ->
                builder.all('buildslaves').bind $scope,
                    dest: builder
                builder.some('builds', {limit:20, order:"-number"}).bind $scope,
                    dest: builder

]

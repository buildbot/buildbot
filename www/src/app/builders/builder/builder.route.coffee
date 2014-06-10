angular.module('buildbot.builders').config ['$stateProvider',
    ($stateProvider) ->

        # Name of the state
        name = 'builder'

        # Configuration
        cfg =
            tabid: 'builders'

        # Register new state
        state =
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/builders/:builder'
            data: cfg

        $stateProvider.state(state)
]

angular.module('buildbot.builders').controller 'builderController',
['$scope', 'buildbotService', '$stateParams', 'resultsService', 'recentStorage'
    ($scope, buildbotService, $stateParams, resultsService, recentStorage) ->
        # make resultsService utilities available in the template
        _.mixin($scope, resultsService)
        builder = buildbotService.one('builders', $stateParams.builder)
        builder.bind($scope).then ->
            recentStorage.addBuilder
                link: '#/builders/' + $scope.builder.builderid
                caption: $scope.builder.name
        builder.all('forceschedulers').bind($scope)
        builder.some('builds', {limit:20, order:"-number"}).bind($scope)
        builder.some('buildrequests', {claimed:0}).bind($scope)
]

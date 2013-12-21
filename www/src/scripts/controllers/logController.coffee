angular.module('app').controller 'logController',
['$log', '$scope', '$location', 'buildbotService', '$stateParams'
    ($log, $scope, $location, buildbotService, $stateParams) ->
        buildbotService.one('builder', $stateParams.builder).get().then (builder) ->
            $scope.builder = builder[0]

        build = buildbotService.one('builder', $stateParams.builder).one('build', $stateParams.build)
        step = build.one('step', $stateParams.step)
        log = step.one('log', $stateParams.log)
        content = log.one('content')
        build.bind($scope, 'build')
        step.bind($scope, 'step')
        log.bind($scope, 'log')
]

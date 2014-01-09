angular.module('app').controller 'buildController',
['$log', '$scope', '$location', 'buildbotService', '$stateParams'
    ($log, $scope, $location, buildbotService, $stateParams) ->

        buildbotService.bindHierarchy($scope, $stateParams, ['builder', 'build'])
        .then ([builder, build]) ->
            build = buildbotService.one('build', build.id)
            build.all('step').bind $scope,
                onchild: (step) ->
                    $scope.$watch (-> step.complete), ->
                        step.fulldisplay = step.complete == 0 || step.results > 0
                    logs = buildbotService.one("step", step.stepid).all("log")
                    logs.bind $scope,
                        dest: step,
            buildbotService.one("buildslave", build.buildslaveid).bind($scope)
]

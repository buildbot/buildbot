angular.module('app').controller 'buildController',
['$log', '$scope', '$location', 'buildbotService', '$stateParams'
    ($log, $scope, $location, buildbotService, $stateParams) ->

        buildbotService.bindHierarchy($scope, $stateParams, ['builders', 'builds'])
        .then ([builder, build]) ->
            build = buildbotService.one('builds', build.id)
            build.all('steps').bind $scope,
                onchild: (step) ->
                    $scope.$watch (-> step.complete), ->
                        step.fulldisplay = step.complete == 0 || step.results > 0
                    logs = buildbotService.one("steps", step.stepid).all("logs")
                    logs.bind $scope,
                        dest: step,
            buildbotService.one("buildslaves", build.buildslaveid).bind($scope)
]

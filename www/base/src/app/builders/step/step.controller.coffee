class Step extends Controller
    constructor: ($log, $scope, $location, buildbotService, $stateParams, glBreadcrumbService) ->
        buildbotService.bindHierarchy($scope, $stateParams, ["builders", "builds", 'steps'])
        .then ([builder, build, step]) ->
            glBreadcrumbService.setBreadcrumb [
                    caption: "Builders"
                    sref: "builders"
                ,
                    caption: builder.name
                    sref: "builder({builder:#{builder.id}})"
                ,
                    caption: build.number
                    sref: "build({builder:#{builder.id}, build:#{build.number}})"
                ,
                    caption: step.name
                    sref: "step({builder:#{builder.id}, build:#{build.number}, step:#{step.number}})"
            ]
            logs = buildbotService.one("steps", step.stepid).all("logs")
            logs.bind $scope,
                dest: step,

class Step extends Controller
    constructor: ($log, $scope, $location, dataService, dataUtilsService, $stateParams, glBreadcrumbService, publicFieldsFilter) ->
        data = dataService.open($scope)
        builderid = dataUtilsService.numberOrString($stateParams.builder)
        buildnumber = dataUtilsService.numberOrString($stateParams.build)
        stepnumber = dataUtilsService.numberOrString($stateParams.step)
        data.getBuilders(builderid).then (builders) ->
            $scope.builder = builder = builders[0]
            builder.getBuilds(buildnumber).then (builds) ->
                $scope.build = build = builds[0]
                build.getSteps(stepnumber).then (steps) ->
                    step = steps[0]
                    glBreadcrumbService.setBreadcrumb [
                        caption: "Builders"
                        sref: "builders"
                    ,
                        caption: builder.name
                        sref: "builder({builder:#{builder.builderid}})"
                    ,
                        caption: build.number
                        sref: "build({builder:#{builder.builderid}, build:#{build.number}})"
                    ,
                        caption: step.name
                        sref: "step({builder:#{builder.builderid}, build:#{build.number}, step:#{step.number}})"
                    ]
                    step.loadLogs()
                    $scope.step = publicFieldsFilter(step)

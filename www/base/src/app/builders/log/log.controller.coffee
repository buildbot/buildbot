class Log extends Controller
    constructor: ($scope, dataService, dataUtilsService, $stateParams, glBreadcrumbService, faviconService) ->
        data = dataService.open().closeOnDestroy($scope)
        $scope.jumpToLine = "end"
        if $stateParams.jump_to_line?
            $scope.jumpToLine = $stateParams.jump_to_line
        builderid = dataUtilsService.numberOrString($stateParams.builder)
        buildnumber = dataUtilsService.numberOrString($stateParams.build)
        stepnumber = dataUtilsService.numberOrString($stateParams.step)
        slug = $stateParams.log
        data.getBuilders(builderid).onNew = (builder) ->
            $scope.builder = builder = builder
            builder.getBuilds(buildnumber).onNew = (build) ->
                $scope.build = build
                build.getSteps(stepnumber).onNew = (step) ->
                    $scope.step = step
                    faviconService.setFavIcon(step)
                    step.getLogs(slug).onNew = (log) ->
                        $scope.log = log
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
                            ,
                                caption: log.name
                                sref: "log({builder:#{builder.builderid}, build:#{build.number}, step:#{step.number}, log:'#{log.slug}'})"
                        ]

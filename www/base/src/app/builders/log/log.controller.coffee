class Log extends Controller
    constructor: ($scope, buildbotService, $stateParams, glBreadcrumbService) ->
        buildbotService.bindHierarchy($scope, $stateParams, ["builders", "builds", 'steps', 'logs'])
        .then ([builder, build, step, log]) ->
            console.log builder, build, step, log
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
                ,
                    caption: log.name
                    sref: "log({builder:#{builder.id}, build:#{build.number}, step:#{step.number}, log:'#{log.slug}'})"
            ]

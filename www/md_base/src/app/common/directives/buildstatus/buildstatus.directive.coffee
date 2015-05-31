class BuildStatus extends Directive

    constructor: ->
        return {
            restrict: 'E'
            templateUrl: 'views/buildstatus.html'
            scope:
                build: '='
            link: (scope) ->
                updateBuild = ->
                    build = scope.build
                    if build.complete is false and build.started_at > 0
                        scope.status_class = 'pending'
                        scope.icon = 'build-pending'
                    else if build.results == 0
                        scope.status_class = 'success'
                        scope.icon = 'build-success'
                    else if build.results == 2 or build.results == 4
                        scope.status_class = 'fail'
                        scope.icon = 'build-fail'
                    else
                        scope.status_class = 'unknown'
                        scope.icon = 'build-pending'
                scope.$watch 'build', updateBuild, true
        }

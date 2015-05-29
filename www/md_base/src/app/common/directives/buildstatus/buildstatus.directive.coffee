class BuildStatus extends Directive

    constructor: ->
        return {
            restrict: 'E'
            templateUrl: 'views/buildstatus.html'
            scope:
                build: '='
            link: (scope) ->
                scope.$watch 'build', ->
                    build = scope.build
                    if build.complete is false and build.started_at > 0
                        scope.status_class = 'pending'
                    else if build.results == 0
                        scope.status_class = 'success'
                    else if build.results == 2 or build.results == 4
                        scope.status_class = 'fail'
                    else
                        scope.status_class = ''
                    console.log scope.status_class
        }

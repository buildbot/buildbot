class BuildStatus extends Directive

    constructor: ->
        return {
            restrict: 'E'
            templateUrl: 'views/buildstatus.html'
            controller: '_BuildStatusController'
            controllerAs: 'status'
            bindToController: true
            scope:
                build: '='
                type: '@'
        }

class _BuildStatus extends Controller

    constructor: ($scope, RESULTS_TEXT) ->
        @type = 'icon' if @type != 'text'

        updateBuild = =>
            build = @build
            if build.complete is false and build.started_at > 0
                @status_class = 'pending'
                @icon = 'build-pending'
            else if build.results == 0
                @status_class = 'success'
                @icon = 'build-success'
            else if build.results == 2 or build.results == 4
                @status_class = 'fail'
                @icon = 'build-fail'
            else
                @status_class = 'unknown'
                @icon = 'build-pending'

            @status_text = RESULTS_TEXT[build.results]
            @status_text ?= 'UNKNOWN'

        $scope.$watch 'status.build', updateBuild, true


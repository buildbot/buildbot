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
            @status_text = RESULTS_TEXT[build.results]
            @status_text ?= 'UNKNOWN'

            if build.complete is false and build.started_at > 0
                @status_class = 'pending'
                @status_text = 'PENDING'
                @icon = 'build-pending'
            else if build.results == 0
                @status_class = 'success'
                @icon = 'build-success'
            else if build.results >= 1 and build.results <= 6
                @status_class = 'fail'
                @icon = 'build-fail'
            else
                @status_class = 'unknown'
                @icon = 'build-pending'

        $scope.$watch 'status.build', updateBuild, true


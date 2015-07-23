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
        }

class _BuildStatus extends Controller

    constructor: ($scope, RESULTS_TEXT) ->
        updateBuild = =>
            build = @build

            if build.complete is false and build.started_at > 0
                @status_class = 'pending'
                @icon = 'pending'
            else if build.results == 0
                @status_class = 'success'
                @icon = 'checkmark'
            else if build.results >= 1 and build.results <= 6
                @status_class = RESULTS_TEXT[build.results].toLowerCase()
                @icon = 'crossmark'
            else
                @status_class = 'unknown'
                @icon = 'pending'

        $scope.$watch 'status.build', updateBuild, true


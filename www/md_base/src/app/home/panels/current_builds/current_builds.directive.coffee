class CurrentBuilds extends Directive

    constructor: ->
        return {
            restrict: 'E'
            templateUrl: 'views/current_builds_panel.html'
            controller: '_CurrentBuildsController'
            controllerAs: 'current'
        }

class _CurrentBuilds extends Controller
    showBuilders: true
    constructor: ($scope, buildbotService, bbSettingsService) ->
        $scope.current_builds = []
        buildbotService.some('builds',
            complete: false
            order:'-started_at'
        ).bind($scope, dest_key:'current_builds')

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
    constructor: ($scope, dataService, bbSettingsService) ->
        data = dataService.open()
        data.closeOnDestroy($scope)

        @builds = data.getBuilds(
            complete: false
            order:'-started_at'
        ).getArray()

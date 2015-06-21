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
        opened = dataService.open()
        opened.closeOnDestroy($scope)

        @builds = opened.getBuilds(
            complete: false
            order:'-started_at'
        ).getArray()

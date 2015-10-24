class RecentBuilds extends Directive

    constructor: ->
        return {
            restrict: 'E'
            controller: '_RecentBuildsController'
            controllerAs: 'recent'
            bindToController: true
            templateUrl: 'views/recent_builds_panel.html'
        }

class _RecentBuilds extends Controller
    showBuilders: true
    constructor: ($scope, dataService, bbSettingsService) ->
        homeSetting = bbSettingsService.getSettingsGroup 'home'

        data = dataService.open()
        data.closeOnDestroy($scope)

        @builds = data.getBuilds(
            complete: true
            order:'-complete_at'
            limit: homeSetting.n_recent_builds.value
        ).getArray()

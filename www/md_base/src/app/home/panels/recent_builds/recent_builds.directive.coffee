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

        opened = dataService.open()
        opened.closeOnDestroy($scope)

        @builds = opened.getBuilds(
            complete: true
            order:'-complete_at'
            limit: homeSetting.n_recent_builds.value
        ).getArray()

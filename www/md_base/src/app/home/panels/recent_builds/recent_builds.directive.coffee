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
    builds: []
    constructor: ($scope, buildbotService, bbSettingsService) ->
        homeSetting = bbSettingsService.getSettingsGroup 'home'

        buildbotService.all('builds').getList(
            complete: true
            order:'-complete_at'
            limit: homeSetting.n_recent_builds.value
        ).then (data) =>
            @builds = data

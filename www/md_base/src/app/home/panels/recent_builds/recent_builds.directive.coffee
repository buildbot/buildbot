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
    constructor: ($scope, buildbotService, bbSettingsService) ->
        homeSetting = bbSettingsService.getSettingsGroup 'home'

        $scope.recent_builds = []
        buildbotService.some('builds',
            complete: true
            order:'-complete_at'
            limit: homeSetting.n_recent_builds.value
        ).bind($scope, dest_key: 'recent_builds')

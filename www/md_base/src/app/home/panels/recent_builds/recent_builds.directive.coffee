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
    builds: []
    constructor: ($scope, buildbotService) ->
        buildbotService.all('builds').getList(
            complete: true
            order:'-complete_at'
            limit: 8
        ).then (data) =>
            @builds = data

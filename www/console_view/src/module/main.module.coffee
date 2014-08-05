name = 'buildbot.console_view'
dependencies = [
    'ui.router'
    'ui.bootstrap'
    'buildbot.common'
    'ngAnimate'
]

# Register new module
m = angular.module name, dependencies
angular.module('app').requires.push(name)

m.config ['$stateProvider',
    ($stateProvider) ->

        # Name of the state
        name = 'console'

        # Configuration
        cfg =
            tabid: name
            tabhash: "##{name}"
            caption: 'Console View'

        # Register new state
        state =
            controller: "#{name}Controller"
            controllerAs: "c"
            templateUrl: "console_view/views/#{name}.html"
            name: name
            url: "/#{name}"
            data: cfg

        $stateProvider.state(state)
]

m.controller 'consoleController', class
        constructor: (@$scope, $q, $window, @buildbotService) ->

            builds = @buildbotService.all('builds').bind @$scope
            builders = @buildbotService.all('builders').bind @$scope
            changes = @buildbotService.all('changes').bind @$scope
            buildrequests = @buildbotService.all('buildrequests').bind @$scope
            buildsets = @buildbotService.all('buildsets').bind @$scope

            $q.all([builds, builders, changes, buildrequests, buildsets])
            .then ([@builds, @builders, @changes, @buildrequests, @buildsets]) =>

                @loading = false

                for change in @changes
                    change.builds = []
                    for builder in @builders
                        change.builds[builder.builderid - 1] =
                            builderid: builder.builderid

                for build in @builds
                    @_matchBuildWithChange(build)

                @_setWidth($window.innerWidth)
                angular.element($window).bind 'resize', =>
                    @_setWidth($window.innerWidth)
                    $scope.$apply()

        loading: true

        _matchBuildWithChange: (build) =>
            buildrequest = @buildrequests[build.buildrequestid - 1]
            buildset = @buildsets[buildrequest.buildsetid - 1]
            if buildrequest? and buildset? and buildset.sourcestamps?
                for sourcestamp in buildset.sourcestamps
                    for change in @changes
                        if change.sourcestamp.ssid == sourcestamp.ssid
                            change.builds[build.builderid - 1] = build

        _setWidth: (width) ->
            @cellWidth = "#{100 / @builders.length}%"
            if (0.85 * width) / @builders.length > 40
                @width = '100%'
            else
                @width = "#{@builders.length * 40 / 0.85}px"

        openAll: ->
            @$scope.$broadcast('showAllInfo', false)

        closeAll: ->
            @$scope.$broadcast('showAllInfo', true)

        showBuilderNames: ->
            @bigHeader = !@bigHeader

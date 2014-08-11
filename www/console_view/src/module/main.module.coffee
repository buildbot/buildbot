# Register new module
class App extends App
    constructor: ->
        return [
            'ui.router'
            'ui.bootstrap'
            'common'
            'ngAnimate'
            'guanlecoja.ui'
        ]

class State extends Config
    constructor: ($stateProvider, glMenuServiceProvider) ->

        # Name of the state
        name = 'console'

        # Menu configuration
        glMenuServiceProvider.addGroup
            name: name
            caption: 'Console View'
            icon: 'exclamation-circle'
            order: 5

        # Configuration
        cfg =
            group: name
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

class Console extends Controller
    constructor: (@$scope, $q, $window, @buildbotService) ->
        builds = @buildbotService.all('builds').bind @$scope
        builders = @buildbotService.all('builders').bind @$scope
        changes = @buildbotService.all('changes').bind @$scope
        buildrequests = @buildbotService.all('buildrequests').bind @$scope
        buildsets = @buildbotService.all('buildsets').bind @$scope

        @loading = true
        $q.all([builds, builders, changes, buildrequests, buildsets])
        .then ([@builds, @builders, @changes, @buildrequests, @buildsets]) =>
            @loading = false

            for change in @changes
                change.builds = []
                for builder in @builders
                    change.builds[builder.builderid - 1] =
                        builderid: builder.builderid

            for build in @builds
                @matchBuildWithChange(build)

            @setWidth($window.innerWidth)
            angular.element($window).bind 'resize', =>
                @setWidth($window.innerWidth)
                $scope.$apply()

    ###
    # Match builds with a change
    ###
    matchBuildWithChange: (build) =>
        buildrequest = @buildrequests[build.buildrequestid - 1]
        buildset = @buildsets[buildrequest.buildsetid - 1]
        if buildrequest? and buildset? and buildset.sourcestamps?
            for sourcestamp in buildset.sourcestamps
                for change in @changes
                    if change.sourcestamp.ssid == sourcestamp.ssid
                        change.builds[build.builderid - 1] = build

    ###
    # Set the content width
    ###
    setWidth: (width) ->
        @cellWidth = "#{100 / @builders.length}%"
        if (0.85 * width) / @builders.length > 40
            @width = '100%'
        else
            @width = "#{@builders.length * 40 / 0.85}px"

    ###
    # Open all change row information
    ###
    openAll: ->
        @$scope.$broadcast('showAllInfo', false)

    ###
    # Close all change row information
    ###
    closeAll: ->
        @$scope.$broadcast('showAllInfo', true)

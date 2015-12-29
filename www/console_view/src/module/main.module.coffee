# Register new module
class App extends App
    constructor: ->
        return [
            'ui.router'
            'ui.bootstrap'
            'common'
            'ngAnimate'
            'guanlecoja.ui'
            'bbData'
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
    constructor: (@$scope, $q, @$window, dataService) ->
        @buildLimit = 200
        @changeLimit = 10
        @dataAccessor = dataService.open().closeOnDestroy(@$scope)

        @$scope.builders = @builders = @dataAccessor.getBuilders()
        @$scope.builders.queryExecutor.isFiltered = (v) ->
            return not v.masterids? or v.masterids.length > 0

        @$scope.builds = @builds = @dataAccessor.getBuilds({limit: @buildLimit, order: '-complete_at'})
        @changes = @dataAccessor.getChanges({limit: @changeLimit, order: '-when_timestamp'})
        @buildrequests = @dataAccessor.getBuildrequests({limit: @buildLimit, order: '-submitted_at'})
        @buildsets = @dataAccessor.getBuildsets({limit: @buildLimit, order: '-submitted_at'})

        @loading = true
        @builds.onChange = @changes.onChange = @buildrequests.onChange = @buildsets.onChange = @onChange

    onChange: (s) =>
        # @todo: no way to know if there are no builds, or if its not yet loaded
        if @builds.length == 0 or @builders.length == 0 or @changes.length == 0 or @buildsets.length == 0 or @buildrequests == 0
            return
        @loading = false

        for build in @builds
            @matchBuildWithChange(build)
        for change in @changes
            change.maxbuilds = 1
            for k, b of change.buildsPerBuilder
                if b.length > change.maxbuilds
                    change.maxbuilds = b.length

        @setWidth(@$window.innerWidth)
        angular.element(@$window).bind 'resize', =>
            @setWidth(@$window.innerWidth)
            @$scope.$apply()

    ###
    # Match builds with a change
    ###
    matchBuildWithChange: (build) =>
        buildrequest = @buildrequests.get(build.buildrequestid)
        if not buildrequest?
            return
        buildset = @buildsets.get(buildrequest.buildsetid)
        if not buildset? or not buildset.sourcestamps?
            return
        for sourcestamp in buildset.sourcestamps
            for change in @changes
                if change.sourcestamp.ssid == sourcestamp.ssid
                    change.buildsPerBuilder ?= {}
                    change.buildsPerBuilder[build.builderid] ?= []
                    if build not in change.buildsPerBuilder[build.builderid]
                        change.buildsPerBuilder[build.builderid].push(build)
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

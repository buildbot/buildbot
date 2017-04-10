# Register new module
class App extends App
    constructor: ->
        return [
            'ui.router'
            'ui.bootstrap'
            'ngAnimate'
            'guanlecoja.ui'
            'bbData'
        ]


class State extends Config
    constructor: ($stateProvider, glMenuServiceProvider, bbSettingsServiceProvider) ->

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

        bbSettingsServiceProvider.addSettingsGroup
            name: 'Console'
            caption: 'Console related settings'
            items: [
                type: 'integer'
                name: 'buildLimit'
                caption: 'Number of builds to fetch'
                default_value: 200
            ,
                type: 'integer'
                name: 'changeLimit'
                caption: 'Number of changes to fetch'
                default_value: 10
            ]

class Console extends Controller
    constructor: (@$scope, $q, @$window, dataService, bbSettingsService, resultsService, @$uibModal) ->
        angular.extend this, resultsService
        settings = bbSettingsService.getSettingsGroup('Console')
        @buildLimit = settings.buildLimit.value
        @changeLimit = settings.changeLimit.value
        @dataAccessor = dataService.open().closeOnDestroy(@$scope)
        @_infoIsExpanded = {}
        @$scope.all_builders = @all_builders = @dataAccessor.getBuilders()
        @$scope.builders = @builders = []

        @$scope.builds = @builds = @dataAccessor.getBuilds
            property: ["got_revision"]
            limit: @buildLimit
            order: '-complete_at'
        @changes = @dataAccessor.getChanges({limit: @changeLimit, order: '-changeid'})
        @buildrequests = @dataAccessor.getBuildrequests({limit: @buildLimit, order: '-submitted_at'})
        @buildsets = @dataAccessor.getBuildsets({limit: @buildLimit, order: '-submitted_at'})

        @builds.onChange = @changes.onChange = @buildrequests.onChange = @buildsets.onChange = @onChange

    onChange: (s) =>
        # if there is no data, no need to try and build something.
        if @builds.length == 0 or @all_builders.length == 0 or @changes.length == 0 or
                @buildsets.length == 0 or @buildrequests == 0
            return

        # we only display builders who actually have builds
        for build in @builds
            @all_builders.get(build.builderid).hasBuild = true

        @builders = []
        for builder in @all_builders
            if builder.hasBuild
                @builders.push(builder)
        @$scope.builders = @builders
        if Intl?
            collator = new Intl.Collator(undefined, {numeric: true, sensitivity: 'base'})
            compare = collator.compare
        else
            compare = (a, b) ->
                return a < b ? -1 : a > b;
        @builders.sort (a, b) -> compare(a.name, b.name)


        @changesBySSID = {}
        for change in @changes
            @changesBySSID[change.sourcestamp.ssid] = change
            @populateChange(change)


        for build in @builds
            @matchBuildWithChange(build)

        @filtered_changes = []
        for ssid, change of @changesBySSID
            for builder in change.builders
                if builder.builds.length>0
                    @filtered_changes.push(change)
                    break
    ###
    # fill a change with a list of builders
    ###
    populateChange: (change) ->
        change.builders = []
        change.buildersById = {}
        for builder in @builders
            builder = builderid:builder.builderid, name:builder.name, builds: []
            change.builders.push(builder)
            change.buildersById[builder.builderid] = builder
    ###
    # Match builds with a change
    ###
    matchBuildWithChange: (build) =>
        buildrequest = @buildrequests.get(build.buildrequestid)
        if not buildrequest?
            return
        buildset = @buildsets.get(buildrequest.buildsetid)
        if  buildset? and buildset.sourcestamps?
            for sourcestamp in buildset.sourcestamps
                change = @changesBySSID[sourcestamp.ssid]

        if not change? and build.properties?.got_revision?
            for codebase, revision of build.properties.got_revision[0]
                change = @makeFakeChange(codebase, revision)

        if not change?
            change = @makeFakeChange("unknown codebase", "unknown revision")

        change.buildersById[build.builderid].builds.push(build)

    makeFakeChange: (codebase, revision) =>
        change = @changesBySSID[revision]
        if not change?
            change = codebase: codebase, revision: revision, changeid: revision, author: "unknown author for " + revision
            @changesBySSID[revision] = change
            @populateChange(change)
        return change
    ###
    # Open all change row information
    ###
    openAll: ->
        for change in @changes
            @_infoIsExpanded[change.changeid] = true

    ###
    # Close all change row information
    ###
    closeAll: ->
        for change in @changes
            @_infoIsExpanded[change.changeid] = false

    ###
    # Calculate row header (aka first column) width
    # depending if we display commit comment, we reserve more space
    ###
    getRowHeaderWidth: ->
        if @hasExpanded()
            return 400  # magic value enough to hold 78 characters lines
        else
            return 200

    ###
    #
    # Determine if we use a 100% width table or if we allow horizontal scrollbar
    # depending on number of builders, and size of window, we need a fixed column size or a 100% width table
    #
    ###
    isBigTable: ->
        padding = @getRowHeaderWidth()
        if ((@$window.innerWidth - padding) / @builders.length) < 40
            return true
        return false
    ###
    #
    # do we have at least one change expanded?
    #
    ###
    hasExpanded: ->
        for change in @changes
            if @infoIsExpanded(change)
                return true
        return false

    ###
    #
    # display build details
    #
    ###
    selectBuild: (build) ->
        modal = @$uibModal.open
            templateUrl: 'console_view/views/modal.html'
            controller: 'consoleModalController as modal'
            windowClass: 'modal-big'
            resolve:
                selectedBuild: -> build

    ###
    #
    # toggle display of additional info for that change
    #
    ###
    toggleInfo: (change)->
        @_infoIsExpanded[change.changeid] = !@_infoIsExpanded[change.changeid]
    infoIsExpanded: (change) ->
        return @_infoIsExpanded[change.changeid]

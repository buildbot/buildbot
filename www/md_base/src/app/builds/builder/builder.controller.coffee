class Builder extends Controller
    info: {}
    builds: []
    lastBuild: {}
    forceschedulers: []
    selectedTab: 0
    buildTabs: []

    tabSelected: (index) ->
        if index == 1
            @loadMoreBuilderInfo()

    selectTab: (tab) ->
        if tab == 'info'
            @selectedTab = 1
        else if tab.match /build\d+/
            match = tab.match /build(\d+)/
            number = parseInt(match[1])
            idx = _.find @buildTabs, (t) -> t.number == number
            if idx >= 0
                @selectedTab = idx + 3 # plus three to skip BUILDS, INFO and divider
            else
                @buildTabs.push number: number
                setTimeout (=> @selectedTab = @buildTabs.length + 2), 200
        else
            @selectedTab = 0

    closeBuildTab: (tab) ->
        idx = @buildTabs.indexOf(tab)
        if idx >= 0
            # switch to former one tab (plus 2 to skip BUILDS, INFO and divider
            @selectedTab = (if idx == 0 then 1 else idx + 2)
            @buildTabs.splice(idx, 1)

    loadMoreBuilderInfo: ->
        return if @moreInfo

        @moreInfo = {}

        @moreInfo.tags = @info.tags
        @moreInfo.description = @info.description
        @moreInfo.slaves = @info.loadBuildslaves().getArray()
        @moreInfo.masters = @info.loadMasters().getArray()
        @moreInfo.forceschedulers = @forceschedulers

    triggerSchedulerDialog: (scheduler, event) ->
        @$mdDialog.show
            parent: document.body
            targetEvent: event
            templateUrl: 'views/builds.forcedialog.html'
            locals:
                scheduler: scheduler
                builder: @info
            controller: 'forceDialogController'
            controllerAs: 'forcedialog'

    updateLastBuild: ->
        lastNumber = @lastBuild.number || -1
        for build in @builds
            if build.number > lastNumber
                @lastBuild = build
                return

    constructor: ($scope, $state, @$mdDialog, @dataService) ->
        opened = dataService.open()
        opened.closeOnDestroy($scope)

        builderid = $state.params.builderid
        tab = $state.params.tab
        @dataService.getBuilders(builderid: builderid).then (data) =>
            if data.length == 0
                alert 'Builder not found!'
                $state.go('builds')
            else
                @info = data[0]
                @forceschedulers = @info.loadForceschedulers().getArray()
                @builds = @info.loadBuilds(
                    builderid: builderid
                    order: '-number'
                    limit: 20
                ).getArray()
                @selectTab(tab)

        $scope.$watch 'builder.builds.length', => @updateLastBuild()
        $scope.$watch 'builder.selectedTab', => @tabSelected(@selectedTab)

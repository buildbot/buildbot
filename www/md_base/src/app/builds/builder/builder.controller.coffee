class Builder extends Controller
    info: {}
    builds: []
    lastBuild: {}
    selectedTab: 0
    selectLock: true
    autoSelect: true
    forceschedulers: []
    buildTabs: []

    tabSelected: (index) ->
        return if @selectLock # avoid loading one page twice
        if index == 0
            @$state.go 'builds.builder.buildstab', builderid: @builderid
        else if index == 1
            @$state.go 'builds.builder.infotab', builderid: @builderid
        else if index == 2
            return # disabled divider tab, just skip
        else if index > 2
            index -= 3
            if index < @buildTabs.length
                @$state.go 'builds.builder.buildtab', {builderid: @builderid, number: @buildTabs[index]}
            else
                @tabSelected(0)

    closeBuildTab: (number) ->
        idx = @buildTabs.indexOf(number)
        @selectedTab = (if idx > 0 then idx + 2 else 1)
        @buildTabs.splice(idx, 1) if idx >=0

    selectTab: (tab, number) ->
        if tab == 'buildstab'
            @selectedTab = 0
        else if tab == 'infotab'
            @selectedTab = 1
        else if tab == 'buildtab'
            idx = @buildTabs.indexOf(number)
            if idx >= 0
                @selectedTab = idx + 3
            else
                @buildTabs.push(number)
        @selectLock = false # unlock select when after selectTab is called for the first time

    loadMoreBuilderInfo: ->
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

    constructor: ($scope, @$state, @$mdDialog, @dataService) ->
        opened = dataService.open()
        opened.closeOnDestroy($scope)

        @builderid = $state.params.builderid
        @dataService.getBuilders(builderid: @builderid).then (data) =>
            if data.length == 0
                alert 'Builder not found!'
                $state.go('builds')
            else
                @info = data[0]
                @forceschedulers = @info.loadForceschedulers().getArray()
                @builds = @info.loadBuilds(
                    builderid: @builderid
                    order: '-number'
                    limit: 20
                ).getArray()
                @loadMoreBuilderInfo()

        $scope.$watch 'builder.builds.length', => @updateLastBuild()
        $scope.$watch 'builder.selectedTab', => @tabSelected(@selectedTab)

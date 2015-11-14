class Builder extends Controller
    selectedTab: 0
    selectLock: true
    autoSelect: true

    constructor: ($scope, @$state, @$mdDialog, @dataService) ->
        @info = {}
        @builds = []
        @lastBuild = {}
        @forceschedulers = []
        @buildTabs = []
        
        data = @dataService.open($scope)

        @builderid = $state.params.builderid
        @dataService.getBuilders(@builderid).then (data) =>
            if data.length == 0
                alert 'Builder not found!'
                $state.go('builds')
            else
                @info = data[0]
                @forceschedulers = @info.loadForceschedulers().getArray()
                @builds = @info.loadBuilds
                    builderid: @builderid
                    order: '-number'
                    limit: 20
                .getArray()
                @loadMoreBuilderInfo()
                
                # go to buildstab if no child state is selected
                if @$state.is('builds.builder', builderid:@builderid)
                    @$state.go 'builds.builder.buildstab', builderid: @builderid

        $scope.$watch 'builder.builds.length', => @updateLastBuild()
        $scope.$watch 'builder.selectedTab', => @tabSelected(@selectedTab)

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
        # We handle build tab first to avoid repeated load as md-tabs will auto select newly added tab
        if tab == 'buildtab'
            idx = @buildTabs.indexOf(number)
            if idx >= 0
                @selectedTab = idx + 3
            else
                @buildTabs.push(number)

        # unlock select when after build tab is handled
        @selectLock = false

        if tab == 'buildstab'
            @selectedTab = 0
        else if tab == 'infotab'
            @selectedTab = 1

    loadMoreBuilderInfo: ->
        @moreInfo =
            tags: @info.tags
            description: @info.description
            slaves: @info.loadBuildslaves().getArray()
            masters: @info.loadMasters().getArray()
            forceschedulers: @forceschedulers

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

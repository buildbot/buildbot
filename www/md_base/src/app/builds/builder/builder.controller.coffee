class Builder extends Controller
    info: {}
    builds: []
    lastBuild: {}
    forceschedulers: []
    selectedTab: 0

    tabSelected: (index) ->
        if index == 1
            @loadMoreBuilderInfo()

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
            controller: 'forceDialogController'
            controllerAs: 'forcedialog'

    constructor: ($scope, $state, @$mdDialog, @dataService) ->
        opened = dataService.open()
        opened.closeOnDestroy($scope)

        builderid = $state.params.builderid
        @dataService.getBuilders(builderid: builderid).then (data) =>
            if data.length == 0
                alert 'Builder not found!'
                $state.go('builds')
            else
                @info = data[0]
                @forceschedulers = @info.loadForceschedulers().getArray()
                @builds = @info.loadBuilds(
                    builderid: builderid
                    order: '-buildid'
                    limit: 20
                ).getArray()

        updateLastBuilder = =>
            @lastBuild = @builds[0] if @builds.length

        $scope.$watch 'builder.builds', updateLastBuilder, true
        $scope.$watch 'builder.selectedTab', (=> @tabSelected(@selectedTab))

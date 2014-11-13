class Builder extends Controller
    constructor: ($rootScope, $scope, buildbotService, $stateParams, resultsService, recentStorage,
        glBreadcrumbService, $state, glTopbarContextualActionsService) ->
        # make resultsService utilities available in the template
        _.mixin($scope, resultsService)
        builder = buildbotService.one('builders', $stateParams.builder)
        builder.bind($scope).then (builder) ->
            breadcrumb = [
                    caption: "Builders"
                    sref: "builders"
                ,
                    caption: builder.name
                    sref: "builder({builder:#{builder.id}})"
            ]
            recentStorage.addBuilder
                link: "#/builders/#{$scope.builder.builderid}"
                caption: $scope.builder.name

            # reinstall breadcrumb when coming back from forcesched
            $scope.$on '$stateChangeSuccess', ->
                glBreadcrumbService.setBreadcrumb(breadcrumb)
            glBreadcrumbService.setBreadcrumb(breadcrumb)

        builder.all('forceschedulers').bind($scope).then (forceschedulers) ->
            actions = []
            _.forEach forceschedulers, (sch) ->
                actions.push
                    caption: sch.name
                    action: -> $state.go("builder.forcebuilder", scheduler:sch.name)

            # reinstall contextual actions when coming back from forcesched
            glTopbarContextualActionsService.setContextualActions(actions)
            $scope.$on '$stateChangeSuccess', ->
                glTopbarContextualActionsService.setContextualActions(actions)

        builder.some('builds', {limit:20, order:"-number"}).bind($scope)
        builder.some('buildrequests', {claimed:0}).bind($scope)

class Builder extends Controller
    constructor: ($rootScope, $scope, dataService, $stateParams, resultsService, recentStorage,
        glBreadcrumbService, $state, glTopbarContextualActionsService) ->
        # make resultsService utilities available in the template
        _.mixin($scope, resultsService)
        data = dataService.open($scope)
        builderid = $stateParams.builder
        data.getBuilders(builderid).then (builders) ->
            builder = builders[0]
            $scope.builder = builder
            breadcrumb = [
                    caption: "Builders"
                    sref: "builders"
                ,
                    caption: builder.name
                    sref: "builder({builder:#{builder.builderid}})"
            ]
            recentStorage.addBuilder
                link: "#/builders/#{builder.builderid}"
                caption: builder.name

            # reinstall breadcrumb when coming back from forcesched
            $scope.$on '$stateChangeSuccess', ->
                glBreadcrumbService.setBreadcrumb(breadcrumb)
            glBreadcrumbService.setBreadcrumb(breadcrumb)

            builder.getForceschedulers().then (forceschedulers) ->
                $scope.forceschedulers = forceschedulers
                actions = []
                _.forEach forceschedulers, (sch) ->
                    actions.push
                        caption: sch.button_name
                        extra_class: "btn-primary"
                        action: -> $state.go("builder.forcebuilder", scheduler:sch.name)

                # reinstall contextual actions when coming back from forcesched
                glTopbarContextualActionsService.setContextualActions(actions)
                $scope.$on '$stateChangeSuccess', ->
                    glTopbarContextualActionsService.setContextualActions(actions)

            $scope.builds = builder.getBuilds(limit:20, order:'-number').getArray()
            $scope.buildrequests = builder.getBuildrequests(claimed:0).getArray()

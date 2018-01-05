class Builders extends Controller
    constructor: ($scope, $log, dataService, resultsService, bbSettingsService, $stateParams,
        $location, dataGrouperService, $rootScope, $filter) ->
        # make resultsService utilities available in the template
        _.mixin($scope, resultsService)
        $scope.connected2class = (worker) ->
            if worker.connected_to.length > 0
                return "worker_CONNECTED"
            else
                return "worker_DISCONNECTED"
        $scope.hasActiveMaster = (builder) ->
            active = false
            if not builder.masterids?
                return false
            for mid in builder.masterids
                m = $scope.masters.get(mid)
                if m? and m.active
                    active = true
            return active
        $scope.settings = bbSettingsService.getSettingsGroup("Builders")
        $scope.$watch('settings', ->
            bbSettingsService.save()
        , true)
        buildFetchLimit = $scope.settings.buildFetchLimit.value

        $scope.getAllTags = ->
            all_tags = []
            for builder in $scope.builders
                if $scope.hasActiveMaster(builder)
                    for tag in builder.tags
                        if all_tags.indexOf(tag) < 0
                            all_tags.push(tag)
            all_tags.sort()
            return all_tags

        updateTagsFilterFromLocation = () ->
            $scope.tags_filter = $location.search()["tags"]
            $scope.tags_filter ?= []
            if not angular.isArray($scope.tags_filter)
                $scope.tags_filter = [$scope.tags_filter]

        updateTagsFilterFromLocation()

        $scope.$watch  "tags_filter", (tags, old) ->
            if old?
                $location.search("tags", tags)
        , true

        $rootScope.$on '$locationChangeSuccess', updateTagsFilterFromLocation

        $scope.isBuilderFiltered = (builder, index) ->

            # filter out inactive builders
            if not $scope.settings.show_old_builders.value and not $scope.hasActiveMaster(builder)
                return false

            pluses = _.filter($scope.tags_filter, (tag) -> tag.indexOf("+") == 0)
            minuses = _.filter($scope.tags_filter, (tag) -> tag.indexOf("-") == 0)

            # First enforce that we have no tag marked '-'
            for tag in minuses
                if builder.tags.indexOf(tag.slice(1)) >= 0
                    return false

            # if only minuses or no filter
            if $scope.tags_filter.length == minuses.length
                return true

            # Then enforce that we have all the tags marked '+'
            for tag in pluses
                if builder.tags.indexOf(tag.slice(1)) < 0
                    return false

            # Then enforce that we have at least one of the tag (marked '+' or not)
            for tag in $scope.tags_filter
                if tag.indexOf("+") == 0
                    tag = tag.slice(1)
                if builder.tags.indexOf(tag) >= 0
                    return true
            return false

        $scope.isTagFiltered = (tag) ->
            return $scope.tags_filter.length == 0 or $scope.tags_filter.indexOf(tag) >= 0 or
                $scope.tags_filter.indexOf('+' + tag) >= 0 or $scope.tags_filter.indexOf('-' + tag) >= 0

        $scope.toggleTag = (tag) ->
            if tag.indexOf('+') == 0
                tag = tag.slice(1)
            if tag.indexOf('-') == 0
                tag = tag.slice(1)
            i = $scope.tags_filter.indexOf(tag)
            iplus = $scope.tags_filter.indexOf("+" + tag)
            iminus = $scope.tags_filter.indexOf("-" + tag)
            if i < 0 and iplus < 0 and iminus < 0
                $scope.tags_filter.push("+" + tag)
            else if iplus >= 0
                $scope.tags_filter.splice(iplus, 1)
                $scope.tags_filter.push('-' + tag)
            else if iminus >= 0
                $scope.tags_filter.splice(iminus, 1)
                $scope.tags_filter.push(tag)
            else
                $scope.tags_filter.splice(i, 1)

        data = dataService.open().closeOnDestroy($scope)

        # as there is usually lots of builders, its better to get the overall
        # list of workers, masters, and builds and then associate by builder
        $scope.builders = data.getBuilders()
        $scope.masters = data.getMasters()
        workers = data.getWorkers()
        builds = null

        requeryBuilds = () ->
            $scope.builders.forEach (builder) -> builder.builds = []

            filteredBuilds = $filter('filter')($scope.builders, $scope.isBuilderFiltered) || []
            builderIds = filteredBuilds.map (builder) -> builder.builderid
            builderIds = [] if builderIds.length == $scope.builders.length

            builds = data.getBuilds(limit: buildFetchLimit, order: '-started_at', builderid__eq: builderIds)
            dataGrouperService.groupBy($scope.builders, workers, 'builderid', 'workers', 'configured_on')
            dataGrouperService.groupBy($scope.builders, builds, 'builderid', 'builds')

        if $scope.tags_filter.length == 0
            requeryBuilds()
        else
            $scope.$watch "builders.$resolved", (resolved) -> requeryBuilds() if resolved

        $scope.$watch "tags_filter", () ->
            if builds && $scope.builders.$resolved
                builds.close()
                requeryBuilds()
        , true
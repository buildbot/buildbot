class Builders extends Controller
    constructor: ($scope, $log, dataService, resultsService, bbSettingsService, $stateParams, $location) ->
        # make resultsService utilities available in the template
        _.mixin($scope, resultsService)
        $scope.connected2class = (slave) ->
            if slave.connected_to.length > 0
                return "slave_CONNECTED"
            else
                return "slave_DISCONNECTED"
        $scope.hasActiveMaster = (builder) ->
            active = false
            if not builder.masters?
                return false
            for m in builder.masters
                if m.active
                    active = true
            return active
        $scope.settings = bbSettingsService.getSettingsGroup("Builders")
        $scope.$watch('settings', ->
            bbSettingsService.save()
        , true)
        $scope.getAllTags = ->
            all_tags = []
            for builder in $scope.builders
                if $scope.hasActiveMaster(builder)
                    for tag in builder.tags
                        if all_tags.indexOf(tag) < 0
                            all_tags.push(tag)
            all_tags.sort()
            return all_tags

        $scope.tags_filter = $location.search()["tags"]
        $scope.tags_filter ?= []
        if not angular.isArray($scope.tags_filter)
            $scope.tags_filter = [$scope.tags_filter]

        $scope.$watch  "tags_filter", (tags, old) ->
            if old?
                $location.search("tags", tags)
        , true

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

        $scope.builders = []
        data = dataService.open($scope)
        byNumber = (a, b) -> return a.number - b.number
        data.getBuilders().then (builders) ->
            $scope.builders = builders
            buildersById = {}
            builders.forEach (builder) ->
                builder.buildslaves = []
                builder.builds = []
                buildersById[builder.builderid] = builder

            # as there is usually lots of builders, its better to get the overall list of slaves
            # and then associate by builder

            #@todo: how could we update this when new slaves are seen?
            data.getBuildslaves().then (slaves) ->
                slaves.forEach (slave) ->
                    slave.configured_on?.forEach (conf) ->
                        buildersById[conf.builderid].buildslaves.push(slave)


            #@todo: how could we update this when new builds are seen?
            data.getBuilds(limit: 200, order: '-started_at').then (builds) ->
                builds.forEach (build) ->
                    buildersById[build.builderid].builds.push(build)
                    buildersById[build.builderid].builds.sort(byNumber)

            # @todo, we cannot do same optims for masters due to lack of data api
            # to map builders and masters
            builders.forEach (builder) ->
                builder.loadMasters()

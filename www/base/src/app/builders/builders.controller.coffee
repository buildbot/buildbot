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
        $log.debug "params", $location.search()

        $scope.$watch  "tags_filter", (tags, old) ->
            if old?
                $log.debug "go", tags
                $location.search("tags", tags)
        , true
        $scope.isBuilderFiltered = (builder, index) ->
            if not $scope.settings.show_old_builders.value and not $scope.hasActiveMaster(builder)
                return false
            if $scope.tags_filter.length == 0
                return true
            for tag in builder.tags
                if $scope.tags_filter.indexOf(tag) >= 0
                    return true
            return false
        $scope.isTagFiltered = (tag) ->
            return $scope.tags_filter.length == 0 or $scope.tags_filter.indexOf(tag) >= 0

        $scope.toggleTag = (tag) ->
            i = $scope.tags_filter.indexOf(tag)
            if i < 0
                $scope.tags_filter.push(tag)
            else
                $scope.tags_filter.splice(i, 1)

        $scope.builders = []
        opened = dataService.open($scope)
        byNumber = (a, b) -> return a.number - b.number
        opened.getBuilders().then (builders) ->
            $scope.builders = builders
            buildersById = {}
            builders.forEach (builder) ->
                builder.buildslaves = []
                builder.builds = []
                buildersById[builder.builderid] = builder

            # as there is usually lots of builders, its better to get the overall list of slaves
            # and then associate by builder

            #@todo: how could we update this when new slaves are seen?
            opened.getBuildslaves().then (slaves) ->
                slaves.forEach (slave) ->
                    slave.configured_on?.forEach (conf) ->
                        buildersById[conf.builderid].buildslaves.push(slave)


            #@todo: how could we update this when new builds are seen?
            opened.getBuilds(limit: 200, order: '-started_at').then (builds) ->
                builds.forEach (build) ->
                    buildersById[build.builderid].builds.push(build)
                    buildersById[build.builderid].builds.sort(byNumber)

            # @todo, we cannot do same optims for masters due to lack of data api
            # to map builders and masters
            builders.forEach (builder) ->
                builder.loadMasters()

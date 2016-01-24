class Builders extends Controller
    constructor: ($scope, $log, dataService, resultsService, bbSettingsService, $stateParams, $location) ->
        # make resultsService utilities available in the template
        _.mixin($scope, resultsService)
        $scope.connected2class = (slave) ->
            if slave.connected_to.length > 0
                return "worker_CONNECTED"
            else
                return "worker_DISCONNECTED"
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

        data = dataService.open().closeOnDestroy($scope)
        byNumber = (a, b) -> return a.number - b.number
        slavesByBuilderId = {}
        buildsByBuilderId = {}

        $scope.builders = data.getBuilders()
        $scope.builders.onNew = (builder) ->
            builder.workers ?= slavesByBuilderId[builder.builderid] || []
            builder.builds ?= buildsByBuilderId[builder.builderid] || []
            builder.loadMasters()

        # as there is usually lots of builders, its better to get the overall list of slaves, and builds
        # and then associate by builder
        # @todo, we cannot do same optims for masters due to lack of data api

        slaves = data.getWorkers()
        slaves.onNew = slaves.onUpdate =  (slave) ->
            slave.configured_on?.forEach (conf) ->
                # the builder might not be yet loaded, so we need to store the slave list
                if $scope.builders.hasOwnProperty(conf.builderid)
                    builder = []
                    slaveslist = $scope.builders.get(conf.builderid).workers ?= []
                else
                    slaveslist = slavesByBuilderId[conf.builderid] ?= []
                slaveslist.push(slave)

        builds = data.getBuilds(limit: 200, order: '-started_at')
        builds.onNew = builds.onUpdate = (build) ->
            # the builder might not be yet loaded, so we need to store the slave list
            if $scope.builders.hasOwnProperty(build.builderid)
                builder = []
                buildslist = $scope.builders.get(build.builderid).builds ?= []
            else
                buildslist = buildsByBuilderId[build.builderid] ?= []
            buildslist.push(build)
            buildslist.sort(byNumber)

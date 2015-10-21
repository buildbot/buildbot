class Builders extends Controller
    constructor: ($scope, buildbotService, resultsService, bbSettingsService, $stateParams, $location) ->
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
        console.log "params", $location.search()

        $scope.$watch  "tags_filter", (tags, old) ->
            if old?
                console.log "go", tags
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
        buildbotService.all('builders').bind $scope,
            onchild: (builder) ->
                builder.all('masters').bind $scope, dest: builder
                builder.all('buildslaves').bind $scope,
                    dest: builder
                builder.some('builds', {limit:20, order:"-number"}).bind $scope,
                    dest: builder

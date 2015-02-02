class Builders extends Controller
    constructor: ($scope, buildbotService, resultsService, bbSettingsService) ->
        # make resultsService utilities available in the template
        _.mixin($scope, resultsService)
        $scope.connected2class = (slave) ->
            if slave.active
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
        console.log $scope.settings
        $scope.$watch('settings', ->
            bbSettingsService.save()
        , true)
        buildbotService.all('builders').bind $scope,
            onchild: (builder) ->
                builder.all('masters').bind $scope, dest: builder
                builder.all('buildslaves').bind $scope,
                    dest: builder
                builder.some('builds', {limit:20, order:"-number"}).bind $scope,
                    dest: builder

class WaterfallModal extends Controller('buildbot.waterfall_view')
    constructor: ($scope, @$modalInstance, @selectedBuild) ->
        $scope.$on '$stateChangeStart', =>
            @close()

    close: ->
        @$modalInstance.close()
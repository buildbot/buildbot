class WaterfallModal extends Controller
    constructor: ($scope, @$uibModalInstance, @selectedBuild) ->
        $scope.$on '$stateChangeStart', =>
            @close()

    close: ->
        @$uibModalInstance.close()
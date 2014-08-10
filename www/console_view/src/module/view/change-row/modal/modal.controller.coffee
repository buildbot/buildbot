class ConsoleModal extends Controller('console_view')
    constructor: ($scope, @$modalInstance, @selectedBuild) ->
        $scope.$on '$stateChangeStart', =>
            @close()

    close: ->
        @$modalInstance.close()
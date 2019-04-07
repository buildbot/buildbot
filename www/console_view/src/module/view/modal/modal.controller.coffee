class ConsoleModal
    constructor: ($scope, @$uibModalInstance, @selectedBuild) ->
        $scope.$on '$stateChangeStart', =>
            @close()

    close: ->
        @$uibModalInstance.close()


angular.module('app')
.controller('consoleModalController', ['$scope', '$uibModalInstance', 'selectedBuild', ConsoleModal])
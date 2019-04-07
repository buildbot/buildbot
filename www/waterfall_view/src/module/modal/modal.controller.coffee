class WaterfallModal
    constructor: ($scope, @$uibModalInstance, @selectedBuild) ->
        $scope.$on '$stateChangeStart', =>
            @close()

    close: ->
        @$uibModalInstance.close()

angular.module('app')
.controller('waterfallModalController', ['$scope', '$uibModalInstance', 'selectedBuild', WaterfallModal])
class ConsoleModalController {
    constructor($scope, $uibModalInstance, selectedBuild) {
        this.$uibModalInstance = $uibModalInstance;
        this.selectedBuild = selectedBuild;
        $scope.$on('$stateChangeStart', () => {
            return this.close();
        });
    }

    close() {
        return this.$uibModalInstance.close();
    }
}

angular.module('console_view')
    .controller('consoleModalController', ['$scope', '$uibModalInstance', 'selectedBuild', ConsoleModalController]);

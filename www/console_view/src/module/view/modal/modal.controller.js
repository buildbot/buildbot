/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class ConsoleModal {
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
.controller('consoleModalController', ['$scope', '$uibModalInstance', 'selectedBuild', ConsoleModal]);

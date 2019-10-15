/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
// a simple service to abstract breadcrumb configuration
class glBreadcrumb {
    constructor($rootScope) {
        this.$rootScope = $rootScope;
    }

    setBreadcrumb(breadcrumb) {
        this.$rootScope.$broadcast("glBreadcrumb", breadcrumb);
    }
}

angular.module('guanlecoja.ui')
.service('glBreadcrumbService', ['$rootScope', glBreadcrumb]);

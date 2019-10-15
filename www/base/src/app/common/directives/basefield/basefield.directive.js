/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
// base widget handling has-error, and error message popups
class Basefield {
    constructor() {
        return {
            replace: true,
            transclude: true,
            restrict: 'E',
            scope: true,
            template: require('./basefield.tpl.jade'),
            controller: '_basefieldController'
        };
    }
}


class _basefield {
    constructor($scope) {
        // clear error on value change
        $scope.$watch("field.value", (o,n) => $scope.field.haserrors = false);

        if ($scope.field.autopopulate) {
            const all = $scope.field.all_fields_by_name;
            // when our field change, we update the fields that we are suppose to
            $scope.$watch("field.value", function(n, o) {
                const autopopulate = $scope.field.autopopulate[n];
                let errors = "";
                if (autopopulate != null) {
                    for (let k in autopopulate) {
                        const v = autopopulate[k];
                        if (all[k] != null) {
                            all[k].value = v;
                        } else {
                            errors += `${k} is not a field name`;
                        }
                    }
                }
                if (errors.length>0) {
                    $scope.field.errors = `bad autopopulate configuration: ${errors}`;
                    $scope.field.haserrors = true;
                }
            });
        }
    }
}

angular.module('common')
.directive('basefield', [Basefield])
.controller('_basefieldController', ['$scope', _basefield]);

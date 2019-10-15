/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */

class Nestedexamplefield {
    constructor() {
        return {
            replace: false,
            restrict: 'E',
            scope: false,
            templateUrl: "nestedexample/views/nestedexamplefield.html",
            controller: '_nestedexamplefieldController'
        };
    }
}

class _nestedexamplefield {
    constructor($scope, $http) {
        // boilerplate to extract our two embedded
        // UI elements

        // the name of the embedded UI elements
        // are prefixed by the type of the root
        // element, "nestedexample" in our case.
        // This method permits to compute that
        // prefixed name.
        const createNestedName = name => `nestedexample_${name}`;

        // utility method to find the embedded
        // field from the scope
        const findNestedElement = function(name) {
            const nameInNestedField = createNestedName(name);
            let res = undefined;
            $scope.field.fields.forEach(function(v, i) {
                if (v.fullName === nameInNestedField) {
                    res = v;
                }
            });
            return res;
        };

        // we put our two embedded fields in the scope
        $scope.pizza = findNestedElement('pizza');
        $scope.ingredients = findNestedElement('ingredients');

        // function that will be called each time a change
        // event happens in the pizza input.
        const ingredientsUrl = pizza => `nestedexample/api/getIngredients?pizza=${pizza}`;

        const updateValues = function(pizza) {
            if (pizza === "") {
                $scope.ingredients.choices = [];
                $scope.ingredients.value = "";
                return;
            }
            $http.get(ingredientsUrl(pizza)).then(function(r) {
                if (r.status === 200) {
                    if (r.data.error != null) {
                        $scope.ingredients.choices = [r.data.error];
                    } else {
                        $scope.ingredients.choices = r.data;
                    }
                } else {
                    const error = `unexpected error got ${r.status}`;
                    $scope.ingredients.choices = [error];
                }
                if ($scope.ingredients.choices.length > 0) {
                    $scope.ingredients.value = $scope.ingredients.choices[0];
                } else {
                    $scope.ingredients.value = "";
                }
            });
        };

        $scope.getIngredients = () => updateValues($scope.pizza.value);
    }
}


angular.module('nestedexample', ['common'])
.directive('nestedexamplefield', [Nestedexamplefield])
.controller('_nestedexamplefieldController', ['$scope', '$http', _nestedexamplefield]);

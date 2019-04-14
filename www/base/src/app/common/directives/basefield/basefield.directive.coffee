# base widget handling has-error, and error message popups
class Basefield
    constructor: ->
        return {
            replace: true
            transclude: true
            restrict: 'E'
            scope: true
            templateUrl: "views/basefield.html"
            controller: '_basefieldController'
        }


class _basefield
    constructor: ($scope) ->
        # clear error on value change
        $scope.$watch "field.value", (o,n) ->
            $scope.field.haserrors = false

        if $scope.field.autopopulate
            all = $scope.field.all_fields_by_name
            # when our field change, we update the fields that we are suppose to
            $scope.$watch "field.value", (n, o) ->
                autopopulate = $scope.field.autopopulate[n]
                errors = ""
                if autopopulate?
                    for k, v of autopopulate
                        if all[k]?
                            all[k].value = v
                        else
                            errors += "#{k} is not a field name"
                if errors.length>0
                    $scope.field.errors = "bad autopopulate configuration: #{errors}"
                    $scope.field.haserrors = true

angular.module('common')
.directive('basefield', [Basefield])
.controller('_basefieldController', ['$scope', _basefield])
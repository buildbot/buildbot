# Register new module
class Nestedexample extends App
    constructor: -> return [
        'common'
    ]

class Nestedexamplefield extends Directive
    constructor: ->
        return {
            replace: false
            restrict: 'E'
            scope: false
            templateUrl: "nestedexample/views/nestedexamplefield.html"
            controller: '_nestedexamplefieldController'
        }

class _nestedexamplefield extends Controller
    constructor: ($scope, $http) ->
        # boilerplate to extract our two embedded
        # UI elements

        # the name of the embedded UI elements
        # are prefixed by the type of the root
        # element, "nestedexample" in our case.
        # This method permits to compute that
        # prefixed name.
        createNestedName = (name) ->
            return "nestedexample_#{name}"

        # utility method to find the embedded
        # field from the scope
        findNestedElement = (name) ->
            nameInNestedField = createNestedName(name)
            res = undefined
            $scope.field.fields.forEach (v, i) ->
                if v.fullName == nameInNestedField
                    res = v
                    return
            return res

        # we put our two embedded fields in the scope
        $scope.pizza = findNestedElement('pizza')
        $scope.ingredients = findNestedElement('ingredients')

        # function that will be called each time a change
        # event happens in the pizza input.
        ingredientsUrl = (pizza) ->
            return "nestedexample/api/getIngredients?pizza=#{pizza}"

        updateValues = (pizza) ->
            if pizza == ""
                $scope.ingredients.choices = []
                $scope.ingredients.value = ""
                return
            $http.get(ingredientsUrl(pizza)).then (r) ->
                if r.status == 200
                    if r.data.error?
                        $scope.ingredients.choices = [r.data.error]
                    else
                        $scope.ingredients.choices = r.data
                else
                    error = "unexpected error got #{r.status}"
                    $scope.ingredients.choices = [error]
                if $scope.ingredients.choices.length > 0
                    $scope.ingredients.value = $scope.ingredients.choices[0]
                else
                    $scope.ingredients.value = ""

        $scope.getIngredients = () ->
            updateValues($scope.pizza.value)

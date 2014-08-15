
# This is the generic plugin-able field implementation
# It will create and compile arbitrary field widget, without
# parent template to have to know each field type in a big ng-switch
# This is done by merging compile and link phasis, so that the template
# includes directives whose types depend on the model.
class Forcefield extends Directive('common')
    constructor: ($log, $compile, RecursionHelper) ->
        return {
            replace: true
            restrict: 'E'
            scope: {field:"="}
            compile: (element, attrs) ->
                return RecursionHelper.compile element, (scope, element, attrs) ->
                    if scope.field.type == 'nested'
                        t = scope.field.layout + "layout"
                    else
                        t = scope.field.type + "field"
                    element.html("<#{t}></#{t}>").show()
                    $compile(element.contents())(scope)
        }

# these directives, combined with "recursive" implement
# the template of recursively nested field groups
_.each ['verticallayout', 'simplelayout', 'tabslayout'],
    (fieldtype) ->
        angular.module('common').directive fieldtype, ->
            replace: true
            restrict: 'E'
            templateUrl: "views/#{fieldtype}.html"
            controller: [ "$scope", ($scope) ->
                # filter out hidden fields, and nested params empty of full of hidden fields
                filtered = []
                for f in $scope.field.fields
                    if f.hide
                        continue
                    if f.type is "nested"
                        all_hidden = true
                        for sf in f.fields
                            if !sf.hide
                                all_hidden = false
                        if all_hidden
                            continue
                    filtered.push(f)
                $scope.field.fields = filtered
                $scope.column_class = 'col-sm-' + (12 / $scope.field.columns).toString()
            ]

# defines standard field directives which only have templates
_.each [ 'textfield' , 'intfield', 'textareafield', 'listfield', 'boolfield'],
    (fieldtype) ->
        angular.module('common').directive fieldtype, ->
            replace: false
            restrict: 'E'
            scope: false
            templateUrl: "views/#{fieldtype}.html"

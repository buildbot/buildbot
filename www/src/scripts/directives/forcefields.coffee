
# This directive allows recursive call of the same directive
# this is used here for forcefield template which is recursively
# called in case of a nested parameter

angular.module("app").directive "recursive", ["$compile", ($compile) ->
    restrict: "A"
    priority: 100000
    compile: (tElement, tAttr) ->
        contents = tElement.contents().remove()
        compiledContents = undefined
        return (scope, iElement, iAttr) ->
            compiledContents = $compile(contents)  unless compiledContents
            iElement.append compiledContents(scope, (clone) ->
                clone
            )
  ]

# This is the generic plugin-able field implementation
# It will create and compile arbitrary field widget, without
# parent template to have to know each field type in a big ng-switch
# This is done by merging compile and link phasis, so that the template
# includes directives whose types depend on the model.
angular.module('app').directive 'forcefield',
['$log', '$compile', ($log, $compile) ->
    replace: true
    restrict: 'E'
    scope: {field:"="}
    compile: (element, attrs) ->
        return (scope, element, attrs) ->
            if scope.field.type == 'nested'
                t = scope.field.layout + "layout"
            else
                t = scope.field.type + "field"
            element.html("<#{t}></#{t}>").show()
            $compile(element.contents())(scope)
]

# these directives, combined with "recursive" implement
# the template of recursively nested field groups
_.each ['verticallayout', 'simplelayout'], (fieldtype) ->
  angular.module('app').directive fieldtype, ->
    replace: true
    restrict: 'E'
    templateUrl: "views/directives/#{fieldtype}.html"
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
_.each [ 'textfield' , 'intfield', 'textareafield', 'listfield', 'boolfield'], (fieldtype) ->
    angular.module('app').directive fieldtype, ->
        replace: false
        restrict: 'E'
        scope: false
        templateUrl: "views/directives/#{fieldtype}.html"

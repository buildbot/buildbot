
# This directive allows recursive call of the same directive
# this is used here for forcefield template which is recursively
# called in case of a nested parameter

angular.module("app").directive "recursive", ["$compile", ($compile) ->
    restrict: "E"
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
# this directive, combined with "recursive" implement
# the template of recursively nested field groups
angular.module('app').directive 'nestedfield', ->
    replace: true
    restrict: 'E'
    scope: {fields:"=", columns:"="}
    templateUrl: 'views/directives/nestedfield.html'
    # we skip the compile phasis which is handled by recursive directive
    compile: ->
        return ->
    controller: [ "$scope", ($scope) ->
        # filter out hidden fields, and nested params empty of full of hidden fields
        filtered = []
        for f in $scope.fields
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
        $scope.fields = filtered
        $scope.column_class = 'col-sm-' + (12 / $scope.columns).toString()
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
            t = scope.field.type + "field"
            element.html("<#{t}></#{t}>").show()
            $compile(element.contents())(scope)
]

# defines standard field directives which only have templates
_.each [ 'textfield' , 'intfield', 'textareafield', 'listfield', 'boolfield'], (fieldtype) ->
    angular.module('app').directive fieldtype, ->
        replace: true
        restrict: 'E'
        scope: true
        templateUrl: "views/directives/#{fieldtype}.html"

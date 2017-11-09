
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

angular.module('common').directive 'filefield', ->
    replace: false
    restrict: 'E'
    scope: false
    # the template uses custom file input styling using trick from
    # https://tympanus.net/codrops/2015/09/15/styling-customizing-file-inputs-smart-way/
    # which basically uses label(for="<id>") to capture the click event and the ugly input(type="file") is just hidden
    templateUrl: "views/filefield.html"
    controller: [ "$scope", ($scope) ->
        # If user selects a big file, then the UI will be completely blocked
        # while browser tries to display it in the textarea
        # so to avoid that we go through a safe value, and play the double binding game
        $scope.$watch "field.value", (value) ->
            if value?.length > 10000
                $scope.field.safevalue = false
            else
                $scope.field.safevalue = value

        $scope.$watch "field.safevalue", (value) ->
            if value? and value != false
                $scope.field.value = value
    ]
angular.module('common').directive 'fileread', ->
    scope: {
        fileread: "="
    },
    # load the file's text via html5 FileReader API
    # note that for simplicity, we don't bother supporting older browsers
    link: (scope, element, attributes) ->
        element.bind "change", (changeEvent) ->
            reader = new FileReader();
            reader.onload = (e) ->
                scope.$apply ->
                    scope.fileread = e.target.result
            reader.readAsText(changeEvent.target.files[0])

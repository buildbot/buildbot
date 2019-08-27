/*
 * decaffeinate suggestions:
 * DS101: Remove unnecessary use of Array.from
 * DS102: Remove unnecessary code created because of implicit returns
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */

// This is the generic plugin-able field implementation
// It will create and compile arbitrary field widget, without
// parent template to have to know each field type in a big ng-switch
// This is done by merging compile and link phasis, so that the template
// includes directives whose types depend on the model.
class Forcefield {
    constructor($log, $compile, RecursionHelper) {
        return {
            replace: true,
            restrict: 'E',
            scope: {field:"="},
            compile(element, attrs) {
                return RecursionHelper.compile(element, function(scope, element, attrs) {
                    let t;
                    if (scope.field.type === 'nested') {
                        t = scope.field.layout + "layout";
                    } else {
                        t = scope.field.type + "field";
                    }
                    element.html(`<${t}></${t}>`).show();
                    return $compile(element.contents())(scope);
                });
            }
        };
    }
}

// these directives, combined with "recursive" implement
// the template of recursively nested field groups
_.each(['verticallayout', 'simplelayout', 'tabslayout'],
    fieldtype =>
        angular.module('common').directive(fieldtype, () =>
            ({
                replace: true,
                restrict: 'E',
                template: require(`./${fieldtype}.tpl.jade`),
                controller: [ "$scope", function($scope) {
                    // filter out hidden fields, and nested params empty of full of hidden fields
                    const filtered = [];
                    for (let f of Array.from($scope.field.fields)) {
                        if (f.hide) {
                            continue;
                        }
                        if (f.type === "nested") {
                            let all_hidden = true;
                            for (let sf of Array.from(f.fields)) {
                                if (!sf.hide) {
                                    all_hidden = false;
                                }
                            }
                            if (all_hidden) {
                                continue;
                            }
                        }
                        filtered.push(f);
                    }
                    $scope.field.fields = filtered;
                    return $scope.column_class = `col-sm-${(12 / $scope.field.columns).toString()}`;
                }
                ]
            })
    )
);

// defines standard field directives which only have templates
_.each([ 'textfield' , 'intfield', 'textareafield', 'listfield', 'boolfield'],
    fieldtype =>
        angular.module('common').directive(fieldtype, () =>
            ({
                replace: false,
                restrict: 'E',
                scope: false,
                template: require(`./${fieldtype}.tpl.jade`),
            })
        )
);

angular.module('common').directive('filefield', () =>
    ({
        replace: false,
        restrict: 'E',
        scope: false,
        // the template uses custom file input styling using trick from
        // https://tympanus.net/codrops/2015/09/15/styling-customizing-file-inputs-smart-way/
        // which basically uses label(for="<id>") to capture the click event and the ugly input(type="file") is just hidden
        template: require('./filefield.tpl.jade'),
        controller: [ "$scope", function($scope) {
            // If user selects a big file, then the UI will be completely blocked
            // while browser tries to display it in the textarea
            // so to avoid that we go through a safe value, and play the double binding game
            $scope.$watch("field.value", function(value) {
                if ((value != null ? value.length : undefined) > 10000) {
                    $scope.field.safevalue = false;
                } else {
                    $scope.field.safevalue = value;
                }
            });

            $scope.$watch("field.safevalue", function(value) {
                if ((value != null) && (value !== false)) {
                    $scope.field.value = value;
                }
            });
        }
        ]
    })
);
angular.module('common').directive('fileread', () =>
    ({
        scope: {
            fileread: "="
        },
        // load the file's text via html5 FileReader API
        // note that for simplicity, we don't bother supporting older browsers
        link(scope, element, attributes) {
            element.bind("change", function(changeEvent) {
                const reader = new FileReader();
                reader.onload = e =>
                    scope.$apply(() => scope.fileread = e.target.result)
                ;
                return reader.readAsText(changeEvent.target.files[0]);
            });
        }
    })
);


angular.module('common')
.directive('forcefield', ['$log', '$compile', 'RecursionHelper', Forcefield]);

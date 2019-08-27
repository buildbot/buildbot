/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class StepController {
    constructor($log, $scope, $location, dataService, dataUtilsService, faviconService, $stateParams, glBreadcrumbService, publicFieldsFilter) {
        const data = dataService.open().closeOnDestroy($scope);
        const builderid = dataUtilsService.numberOrString($stateParams.builder);
        const buildnumber = dataUtilsService.numberOrString($stateParams.build);
        const stepnumber = dataUtilsService.numberOrString($stateParams.step);
        data.getBuilders(builderid).then(function(builders) {
            let builder;
            $scope.builder = (builder = builders[0]);
            builder.getBuilds(buildnumber).then(function(builds) {
                let build;
                $scope.build = (build = builds[0]);
                build.getSteps(stepnumber).then(function(steps) {
                    const step = steps[0];
                    faviconService.setFavIcon(step);
                    glBreadcrumbService.setBreadcrumb([{
                        caption: "Builders",
                        sref: "builders"
                    }
                    , {
                        caption: builder.name,
                        sref: `builder({builder:${builder.builderid}})`
                    }
                    , {
                        caption: build.number,
                        sref: `build({builder:${builder.builderid}, build:${build.number}})`
                    }
                    , {
                        caption: step.name,
                        sref: `step({builder:${builder.builderid}, build:${build.number}, step:${step.number}})`
                    }
                    ]);
                    step.loadLogs();
                    $scope.step = publicFieldsFilter(step);
                });
            });
        });
    }
}


angular.module('app')
.controller('stepController', ['$log', '$scope', '$location', 'dataService', 'dataUtilsService', 'faviconService', '$stateParams', 'glBreadcrumbService', 'publicFieldsFilter', StepController]);

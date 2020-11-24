/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class LogController {
    constructor($scope, dataService, dataUtilsService, $stateParams, glBreadcrumbService, faviconService) {
        const data = dataService.open().closeOnDestroy($scope);
        $scope.jumpToLine = "end";
        if ($stateParams.jump_to_line != null) {
            $scope.jumpToLine = $stateParams.jump_to_line;
        }
        const builderid = dataUtilsService.numberOrString($stateParams.builder);
        const buildnumber = dataUtilsService.numberOrString($stateParams.build);
        const stepnumber = dataUtilsService.numberOrString($stateParams.step);
        const slug = $stateParams.log;

        // Clear breadcrumb on destroy
        $scope.$on('$destroy', () => glBreadcrumbService.setBreadcrumb([]));

        data.getBuilders(builderid).onNew = function(builder) {
            $scope.builder = (builder = builder);
            builder.getBuilds(buildnumber).onNew = function(build) {
                $scope.build = build;
                build.getSteps(stepnumber).onNew = function(step) {
                    $scope.step = step;
                    faviconService.setFavIcon(step);
                    step.getLogs(slug).onNew = function(log) {
                        $scope.log = log;
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
                            ,
                                {caption: step.name}
                            , {
                                caption: log.name,
                                sref: `log({builder:${builder.builderid}, build:${build.number}, step:${step.number}, log:'${log.slug}'})`
                            }
                        ]);
                    };
                };
            };
        };
    }
}


angular.module('app')
.controller('logController', ['$scope', 'dataService', 'dataUtilsService', '$stateParams', 'glBreadcrumbService', 'faviconService', LogController]);

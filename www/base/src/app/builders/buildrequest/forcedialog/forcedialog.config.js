/*
 * decaffeinate suggestions:
 * DS101: Remove unnecessary use of Array.from
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class ForceDialogState {
    constructor($stateProvider) {
        $stateProvider.state("builder.forcebuilder", {
            url: "/force/:scheduler",
            onEnter: ['$stateParams', '$state', '$uibModal',
                      function($stateParams, $state, $uibModal) {
                const modal = {};
                modal.modal = $uibModal.open({
                    template: require('./forcedialog.tpl.jade'),
                    controller: 'forceDialogController',
                    windowClass: 'modal-xlg',
                    resolve: {
                        builderid() { return $stateParams.builder; },
                        schedulerid() { return $stateParams.scheduler; },
                        modal() { return modal; }
                    }
                });

                // We exit the state if the dialog is closed or dismissed
                const goBuild = function(result) {
                    const [ buildsetid, brids ] = Array.from(result);
                    const buildernames = _.keys(brids);
                    if (buildernames.length === 1) {
                        return $state.go("buildrequest", {
                            buildrequest: brids[buildernames[0]],
                            redirect_to_build: true
                        }
                        );
                    }
                };
                const goUp = result => $state.go("^");

                return modal.modal.result.then(goBuild, goUp);
            }]
        }
        );
    }
}


angular.module('app')
.config(['$stateProvider', ForceDialogState]);

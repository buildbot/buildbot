/*
 * decaffeinate suggestions:
 * DS101: Remove unnecessary use of Array.from
 * DS102: Remove unnecessary code created because of implicit returns
 * DS205: Consider reworking code to avoid use of IIFEs
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class WorkerActionState {
    constructor($stateProvider, bbSettingsServiceProvider) {
        const states = [{
            name: "worker.actions",
            multiple: false
        }
        , {
            name: "workers.actions",
            multiple: true
        }
        ];
        states.forEach(state =>
            $stateProvider.state(state.name, {
                url: "/actions",
                data: { group: null },
                onEnter: ['$stateParams', '$state', '$uibModal', 'dataService', '$q',
                          function($stateParams, $state, $uibModal, dataService, $q) {
                    const modal = {};
                    modal.modal = $uibModal.open({
                        template: require('./workeractions.tpl.jade'),
                        controller: 'workerActionsDialogController',
                        windowClass: 'modal-xlg',
                        resolve: {
                            workerid() { return $stateParams.worker; },
                            schedulerid() { return $stateParams.scheduler; },
                            multiple() { return state.multiple; },
                            modal() { return modal; },
                            workers() {
                                const d = $q.defer();
                                dataService.getWorkers({subscribe: false}).onChange = function(workers) {
                                    workers.then = undefined;  // angular will try to call it if it exists
                                    d.resolve(workers);
                                };
                                return d.promise;
                            }
                        }
                    });

                    const goUp = result => $state.go("^");

                    return modal.modal.result.then(goUp, goUp);
                }]
            }
            )
        );
    }
}

class workerActionsDialog {
    constructor($scope, config, $state, modal, workerid, multiple, $rootScope, $q, workers) {
        let worker;
        let w;
        $scope.select_options = [];
        $scope.worker_selection = [];
        if (!multiple) {
            worker = workers.get(workerid);
            $scope.worker_selection.push(worker.name);
            $scope.stop_disabled = worker.connected_to.length === 0;
            $scope.pause_disabled = worker.paused;
            $scope.unpause_disabled = !worker.paused;
        } else {
            $scope.stop_disabled = false;
            $scope.pause_disabled = false;
            $scope.unpause_disabled = false;
        }
        angular.extend($scope, {
            multiple,
            worker,
            select_options: (((() => {
                const result = [];
                for (w of Array.from(workers)) {                     result.push(w.name);
                }
                return result;
            })())),
            action(a){
                const dl = [];
                workers.forEach(function(w) {
                    if (Array.from($scope.worker_selection).includes(w.name)) {
                        const p = w.control(a, {reason: $scope.reason});
                        p.catch(function(err) {
                            let msg = `unable to ${a} worker ${w.name}:`;
                            msg += err.error.message;
                            $scope.error = msg;
                        });
                        dl.push(p);
                    }
                });
                return $q.all(dl).then(res => modal.modal.close(res.result));
            },
            cancel() {
                return modal.modal.dismiss();
            }
        }
        );
    }
}


angular.module('app')
.config(['$stateProvider', 'bbSettingsServiceProvider', WorkerActionState])
.controller('workerActionsDialogController', ['$scope', 'config', '$state', 'modal', 'workerid', 'multiple', '$rootScope', '$q', 'workers', workerActionsDialog]);

/*
 * decaffeinate suggestions:
 * DS101: Remove unnecessary use of Array.from
 * DS102: Remove unnecessary code created because of implicit returns
 * DS205: Consider reworking code to avoid use of IIFEs
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class forceDialog {
    constructor($scope, config, $state, modal, schedulerid, $rootScope, builderid, dataService) {
        dataService.getForceschedulers(schedulerid, {subscribe: false}).onChange = function(schedulers) {
            const scheduler = schedulers[0];
            const all_fields_by_name = {};

            // prepare default values
            var prepareFields = fields => {
                for (let field of Array.from(fields)) {
                    all_fields_by_name[field.fullName] = field;
                    // give a reference of other fields to easily implement
                    // autopopulate
                    field.all_fields_by_name = all_fields_by_name;
                    field.errors = '';
                    field.haserrors = false;
                    if (field.fields != null) {
                        prepareFields(field.fields);
                    } else {
                        field.value = field.default;
                        // if field type is username, then we just hide the field
                        // the backend will fill the value automatically
                        if (field.type === 'username') {
                            field.type = "text";
                            const { user } = config;
                            if (user.email != null) {
                                field.type = "text";
                                field.hide = true;
                            }
                        }
                    }
                }
            };

            prepareFields(scheduler.all_fields);
            angular.extend($scope, {
                rootfield: {
                    type: 'nested',
                    layout: 'simple',
                    fields: scheduler.all_fields,
                    columns: 1
                },
                sch: scheduler,
                startDisabled: false,
                ok() {
                    if ($scope.startDisabled == true) {
                        // prevent multiple executions of scheduler
                        return null;
                    };
                    $scope.startDisabled = true;
                    const params =
                        {builderid};
                    for (let name in all_fields_by_name) {
                        const field = all_fields_by_name[name];
                        params[name] = field.value;
                    }

                    return scheduler.control('force', params)
                    .then(res => modal.modal.close(res.result), function(err) {
                        $scope.startDisabled = false;
                        if (err === null) {
                            return;
                        }
                        if (err.error.code === -32602) {
                            for (let k in err.error.message) {
                                const v = err.error.message[k];
                                all_fields_by_name[k].errors = v;
                                all_fields_by_name[k].haserrors = true;
                            }
                        } else {
                            $scope.error = err.error.message;
                        }
                    });
                },
                cancel() {
                    return modal.modal.dismiss();
                }
            }
            );
        };
    }
}


angular.module('app')
.controller('forceDialogController', ['$scope', 'config', '$state', 'modal', 'schedulerid', '$rootScope', 'builderid', 'dataService', forceDialog]);

class Step {
    constructor(Base, dataService) {
        let BuildInstance;
        return (BuildInstance = class BuildInstance extends Base {
            constructor(object, endpoint) {
                const endpoints = [
                    'logs'           // /logs
                ];

                super(object, endpoint, endpoints);
            }
        });
    }
}


angular.module('app')
.factory('Step', ['Base', 'dataService', Step]);
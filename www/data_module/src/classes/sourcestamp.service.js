class Sourcestamp {
    constructor(Base, dataService) {
        let SourcestampInstance;
        return (SourcestampInstance = class SourcestampInstance extends Base {
            constructor(object, endpoint) {
                const endpoints = [
                    'changes'           // /changes
                ];

                super(object, endpoint, endpoints);
            }
        });
    }
}


angular.module('bbData')
.factory('Sourcestamp', ['Base', 'dataService', Sourcestamp]);

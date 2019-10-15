// damn grammar. I claim that properties singular is propertie
class Propertie {
    constructor(Base, dataService) {
        let BuildInstance;
        return (BuildInstance = class BuildInstance extends Base {
            constructor(object, endpoint) {
                super(object, endpoint, []);
            }
        });
    }
}


angular.module('bbData')
.factory('Propertie', ['Base', 'dataService', Propertie]);

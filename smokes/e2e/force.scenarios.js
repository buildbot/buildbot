// test goal: checks the capability to define a reason and to cancel/start the build

const forcePage = require('./pages/force.js');
const builderPage = require('./pages/builder.js');
const homePage = require('./pages/home.js');

describe('force', function() {
    let force = null;
    let builder = null;

    beforeEach(function() {
        builder = new builderPage('runtests', 'force');
        force =  new forcePage();
        return builder.goDefault();
    });
    afterEach(() => new homePage().waitAllBuildsFinished());

    let lastbuild = null;
    it('should create a build', function() {

        lastbuild = 0;
        builder.go();
        builder.getLastSuccessBuildNumber().then(function(lastbuild) {
            builder.goForce();
            force.getStartButton().click();
            builder.go();
            builder.waitNextBuildFinished(lastbuild);
        });
    });
});

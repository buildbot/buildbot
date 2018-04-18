// test goal: checks the capability to define a reason and to cancel/start the build

const homePage = require('./pages/home.js');
const forcePage = require('./pages/force.js');
const builderPage = require('./pages/builder.js');

describe('force and cancel', function() {
    let force = null;
    let builder = null;

    beforeEach(function() {
        builder = new builderPage('runtests', 'force');
        force =  new forcePage();
        return builder.goDefault();
    });

    afterEach(() => new homePage().waitAllBuildsFinished());

    it('should create a build', function() {
        builder.go();
        builder.getLastSuccessBuildNumber().then(function(lastbuild) {
            builder.goForce();
            force.getStartButton().click();
            builder.go();
            builder.waitNextBuildFinished(lastbuild);
        });
    });

    it('should create a build with a dedicated reason and cancel it', function() {

        builder.go();
        builder.goForce();
        force.getCancelButton().click();
    });

    it('should create a build with a dedicated reason and Start it', function() {

        builder.go();
        builder.goForce();
        force.setReason("New Test Reason");
        force.setYourName("FaceLess User");
        force.setProjectName("BBOT9");
        force.setBranchName("Gerrit Branch");
        force.setRepo("http//name.com");
        force.setRevisionName("12345");
        force.getStartButton().click();
    });
});

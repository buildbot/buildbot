// test goal: checks the capability to navigate in a dedicated build
// to use previous and next link


const homePage = require('./pages/home.js');
const forcePage = require('./pages/force.js');
const builderPage = require('./pages/builder.js');

describe('rebuilds', function() {
    let force = null;
    let builder = null;

    beforeEach(function() {
        builder = new builderPage('runtests', 'force');
        force =  new forcePage();
        return builder.goDefault();
    });

    afterEach(() => new homePage().waitAllBuildsFinished());

    it('should navigate to a dedicated build and to use the rebuild button', function() {
        builder.go();
        return builder.getLastSuccessBuildNumber().then(function(lastbuild) {
            builder.goForce();
            force.getStartButton().click();
            builder.go();
            builder.waitNextBuildFinished(lastbuild);
            builder.goBuild(lastbuild);
            browser.getCurrentUrl().then(function(buildUrl) {
                builder.getRebuildButton().click();
                builder.waitGoToBuild(lastbuild+2);
            });
        });
    });
});

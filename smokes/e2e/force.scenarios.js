/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
// coffee script
// test goal: checks the capability to define a reason and to cancel/start the build

const forcePage = require('./pages/force.coffee');
const builderPage = require('./pages/builder.coffee');
const homePage = require('./pages/home.coffee');

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
    return it('should create a build', function() {

        lastbuild = 0;
        builder.go();
        return builder.getLastSuccessBuildNumber().then(function(lastbuild) {
            builder.goForce();
            force.getStartButton().click();
            builder.go();
            return builder.waitNextBuildFinished(lastbuild);
        });
    });
});

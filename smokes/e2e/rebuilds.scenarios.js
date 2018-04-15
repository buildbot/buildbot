/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
// coffee script
// test goal: checks the capability to navigate in a dedicated build
// to use previous and next link


const homePage = require('./pages/home.coffee');
const forcePage = require('./pages/force.coffee');
const builderPage = require('./pages/builder.coffee');

describe('rebuilds', function() {
    let force = null;
    let builder = null;

    beforeEach(function() {
        builder = new builderPage('runtests', 'force');
        force =  new forcePage();
        return builder.goDefault();
    });

    afterEach(() => new homePage().waitAllBuildsFinished());

    return it('should navigate to a dedicated build and to use the rebuild button', function() {
        builder.go();
        return builder.getLastSuccessBuildNumber().then(function(lastbuild) {
            builder.goForce();
            force.getStartButton().click();
            builder.go();
            builder.waitNextBuildFinished(lastbuild);
            builder.goBuild(lastbuild);
            return browser.getCurrentUrl().then(function(buildUrl) {
                builder.getRebuildButton().click();
                return builder.waitGoToBuild(lastbuild+2);
            });
        });
    });
});

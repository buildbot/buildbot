// test goal: checks the capability to navigate in a dedicated build
// to use previous and next link


import { ForcePage } from './pages/force';
import { BuilderPage } from './pages/builder';
import { HomePage } from './pages/home';

describe('previousnextlink', function() {
    let force = null;
    let builder = null;

    beforeEach(function() {
        builder = new BuilderPage('runtests', 'force');
        return force =  new ForcePage();
    });
    afterEach(() => new HomePage().waitAllBuildsFinished());

    it('has afterEach working', function() {
    });

    it('should navigate in the builds history by using the previous next links', function() {
        builder.go();
        builder.getLastSuccessBuildNumber().then(function(lastbuild) {
            // Build #1
            builder.goForce();
            force.getStartButton().click();
            builder.go();
            builder.waitNextBuildFinished(lastbuild);
            // Build #2
            builder.goForce();
            force.getStartButton().click();
            builder.go();
            builder.waitNextBuildFinished(+lastbuild + 1);
            builder.goBuild(+lastbuild + 2);
            const lastBuildURL = browser.getCurrentUrl();
            builder.clickWhenClickable(builder.getPreviousButton());
            expect(browser.getCurrentUrl()).not.toMatch(lastBuildURL);
            builder.clickWhenClickable(builder.getNextButton());
            expect(browser.getCurrentUrl()).toMatch(lastBuildURL);
        });
    });
});

describe('forceandstop', function() {
    let force = null;
    let builder = null;

    beforeEach(function() {
        builder = new BuilderPage('slowruntests', 'force');
        return force =  new ForcePage();
    });

    it('should create a build with a dedicated reason and stop it during execution', function() {

        builder.goForce();
        force.getStartButton().click();
        expect(browser.getCurrentUrl()).toMatch("/builders/\[1-9]/builds/\[1-9]");
        builder.getStopButton().click();
    });
});

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
    afterEach(async () => {
        const homePage = new HomePage();
        await homePage.waitAllBuildsFinished();
    });

    it('has afterEach working', function() {
    });

    it('should navigate in the builds history by using the previous next links', async () => {
        await builder.go();
        const lastbuild = await builder.getLastSuccessBuildNumber();
        // Build #1
        await builder.goForce();
        await force.getStartButton().click();
        await builder.go();
        await builder.waitNextBuildFinished(lastbuild);
        // Build #2
        await builder.goForce();
        await force.getStartButton().click();
        await builder.go();
        await builder.waitNextBuildFinished(+lastbuild + 1);
        await builder.goBuild(+lastbuild + 2);
        const lastBuildURL = await browser.getCurrentUrl();
        await builder.clickWhenClickable(builder.getPreviousButton());
        expect(await browser.getCurrentUrl()).not.toMatch(lastBuildURL);
        await builder.clickWhenClickable(builder.getNextButton());
        expect(await browser.getCurrentUrl()).toMatch(lastBuildURL);
    });
});

describe('forceandstop', function() {
    let force = null;
    let builder = null;

    beforeEach(function() {
        builder = new BuilderPage('slowruntests', 'force');
        return force =  new ForcePage();
    });

    it('should create a build with a dedicated reason and stop it during execution', async () => {

        await builder.goForce();
        await force.getStartButton().click();
        expect(await browser.getCurrentUrl()).toMatch("/builders/\[1-9]/builds/\[1-9]");
        await builder.getStopButton().click();
    });
});

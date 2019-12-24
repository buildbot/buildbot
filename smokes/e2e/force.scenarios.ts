// test goal: checks the capability to define a reason and to cancel/start the build

import { ForcePage } from './pages/force';
import { BuilderPage } from './pages/builder';
import { HomePage } from './pages/home';
import { browser, by, element, ExpectedConditions as EC } from 'protractor';

describe('force', function() {
    let force = null;
    let builder = null;

    beforeEach(async () => {
        builder = new BuilderPage('runtests', 'force');
        force =  new ForcePage();
        await builder.goDefault();
    });

    afterEach(async () => {
        const homePage = new HomePage();
        await homePage.waitAllBuildsFinished();
    });

    it('should create a build', async () => {
        let lastbuild = 0;
        await builder.go();
        lastbuild = await builder.getLastFinishedBuildNumber();
        await builder.goForce();
        await force.clickStartButtonAndWaitRedirectToBuild();
        await builder.go();
        await builder.waitNextBuildFinished(lastbuild);
    });
});

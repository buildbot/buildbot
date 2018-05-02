// test goal: checks the capability to define a reason and to cancel/start the build

import { ForcePage } from './pages/force';
import { BuilderPage } from './pages/builder';
import { HomePage } from './pages/home';

describe('force', function() {
    let force = null;
    let builder = null;

    beforeEach(function() {
        builder = new BuilderPage('runtests', 'force');
        force =  new ForcePage();
        return builder.goDefault();
    });

    afterEach(async () => {
        const homePage = new HomePage();
        await homePage.waitAllBuildsFinished();
    });

    it('should create a build', async () => {
        let lastbuild = 0;
        await builder.go();
        lastbuild = await builder.getLastSuccessBuildNumber();
        await builder.goForce();
        await force.getStartButton().click();
        await builder.go();
        await builder.waitNextBuildFinished(lastbuild);
    });
});

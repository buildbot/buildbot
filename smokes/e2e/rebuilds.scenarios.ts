// test goal: checks the capability to navigate in a dedicated build
// to use previous and next link


import { HomePage } from './pages/home';
import { ForcePage } from './pages/force';
import { BuilderPage } from './pages/builder';

describe('rebuilds', function() {
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

    it('should navigate to a dedicated build and to use the rebuild button', async () => {
        await builder.go();
        const lastbuild: number = await builder.getLastSuccessBuildNumber();
        await builder.goForce();
        await force.getStartButton().click();
        await builder.go();
        await builder.waitNextBuildFinished(lastbuild);
        await builder.goBuild(lastbuild);
        await browser.getCurrentUrl();
        await builder.getRebuildButton().click();
        await builder.waitGoToBuild(lastbuild + 2);
    });
});

// test goal: checks the capability to navigate in a dedicated build
// to use previous and next link


import { ForcePage } from './pages/force';
import { BuilderPage } from './pages/builder';
import { WaterfallPage } from './pages/waterfall';
import { HomePage } from './pages/home';
import { SettingsPage } from './pages/settings';

describe('waterfall', function() {
    let force = null;
    let builder = null;
    let waterfall = null;

    beforeEach(async () => {
        builder = new BuilderPage('runtests', 'force');
        force =  new ForcePage();
        waterfall = new WaterfallPage('runtests');
        const settings =  new SettingsPage('runtests');
        await settings.goSettings();
        await settings.changeScallingFactor('10');
        await settings.changeColumnWidth('45');
    });

    afterEach(async () => {
        const homePage = new HomePage();
        await homePage.waitAllBuildsFinished();
    });

    const createBuildAndWaitForFinish = async () => {
        await builder.go();
        const lastbuildid = await builder.getLastFinishedBuildNumber();
        await builder.goForce();
        await force.clickStartButtonAndWaitRedirectToBuild();
        await builder.go();
        await builder.waitBuildFinished(lastbuildid + 1);
    };

    it('can go to builder page via hyperlink', async () => {
        await createBuildAndWaitForFinish();
        await waterfall.go();
        await waterfall.goBuilderAndCheck('runtests');
    });

    it('can go to build page via hyperlink in build modal dialog', async () => {
        await createBuildAndWaitForFinish();
        await waterfall.go();
        await waterfall.goBuildAndCheck();
    });

    it('can open build modal dialog and close it', async () => {
        await createBuildAndWaitForFinish();
        await waterfall.go();
        await waterfall.goBuildAndClose();
    });

    it('does url change once tag clicked', async () => {
        await createBuildAndWaitForFinish();
        await waterfall.go();
        await waterfall.goTagAndCheckUrl();
    });

    it('is tag clicked when url contains tag', async () => {
        await createBuildAndWaitForFinish();
        await waterfall.go();
        await waterfall.goUrlAndCheckTag();
    });
});

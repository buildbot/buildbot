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

    beforeEach(function() {
        builder = new BuilderPage('runtests', 'force');
        force =  new ForcePage();
        waterfall = new WaterfallPage('runtests');
        const settings =  new SettingsPage('runtests');
        settings.goSettings();
        settings.changeScallingFactor('10');
        settings.changeColumnWidth('45');
    });

    afterEach(() => new HomePage().waitAllBuildsFinished());

    it('should navigate to the waterfall, check one builder and hyperlink', function() {
        waterfall.go();
        waterfall.goBuilderAndCheck('runtests');
    });

    it('should navigate to the builds waterfall and check the associated hyperlink', function() {
        waterfall.go();
        waterfall.goBuildAndCheck();
    });

    it('should navigate to the builds waterfall and open the popup and close it', function() {
        waterfall.go();
        waterfall.goBuildAndClose();
    });
});

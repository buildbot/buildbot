import { browser, by, element, ExpectedConditions as EC } from 'protractor';
import { ConsolePage } from './pages/console';
import { BuilderPage } from './pages/builder';
import { HomePage } from './pages/home';

describe('change hook', function() {
    let builder = null;
    let console = null;
    beforeEach(function() {
        builder = new BuilderPage('runtests1', 'force');
        return console = new ConsolePage();
    });

    afterEach(async () => {
        const homePage = new HomePage();
        await homePage.waitAllBuildsFinished();
    });

    it('should create a build', async () => {
        await builder.go();
        let lastbuild = await builder.getLastSuccessBuildNumber();
        await browser.executeAsyncScript((done) =>
            $.post('change_hook/base', {
                comments:'sd',
                project:'pyflakes',
                repository:'git://github.com/buildbot/hello-world.git',
                author:'foo <foo@bar.com>',
                revision: 'HEAD',
                branch:'master'
                }, done)
        );
        await builder.waitNextBuildFinished(lastbuild);
        await console.go();
        expect(await console.countSuccess()).toBeGreaterThan(0);
    });
});

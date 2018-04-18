const consolePage = require('./pages/console.js');
const builderPage = require('./pages/builder.js');
const homePage = require('./pages/home.js');

describe('change hook', function() {
    let builder = null;
    let console = null;
    beforeEach(function() {
        builder = new builderPage('runtests1', 'force');
        return console = new consolePage();
    });
    afterEach(() => new homePage().waitAllBuildsFinished());

    it('should create a build', function() {
        builder.go();
        builder.getLastSuccessBuildNumber().then(function(lastbuild) {
            browser.executeAsyncScript(done=>
                $.post('change_hook/base', {
                    comments:'sd',
                    project:'pyflakes',
                    repository:'git://github.com/buildbot/hello-world.git',
                    author:'foo <foo@bar.com>',
                    revision: 'HEAD',
                    branch:'master'
                    }, done)
            );
            return builder.waitNextBuildFinished(lastbuild);
        });
        console.go();
        expect(console.countSuccess()).toBeGreaterThan(0);
    });
});

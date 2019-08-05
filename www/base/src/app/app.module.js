import '@uirouter/angularjs';
import 'angular-animate';
import 'angular-bootstrap-multiselect';
import 'angular-recursion';
import 'angular-ui-bootstrap';
import 'guanlecoja-ui';
import 'buildbot-data-js';

class App {
    constructor() { return [
        'buildbot_config',
        'ngAnimate',
        'ui.bootstrap',
        'ui.router',
        'RecursionHelper',
        'guanlecoja.ui',
        'bbData',
        'btorfs.multiselect'
    ]; }
}


angular.module('app', new App());

// require common module first because it declares a new module other files will need
require('./common/common.module.js');

require('./about/about.controller.js');
require('./about/about.route.js');
require('./app.route.js');
require('./app.run.js');
require('./builders/builder/builder.controller.js');
require('./builders/builder/builder.route.js');
require('./builders/builders.controller.js');
require('./builders/builders.route.js');
require('./builders/buildrequest/buildrequest.controller.js');
require('./builders/buildrequest/buildrequest.route.js');
require('./builders/buildrequest/forcedialog/forcedialog.config.js');
require('./builders/buildrequest/forcedialog/forcedialog.controller.js');
require('./builders/builds/build.controller.js');
require('./builders/builds/build.route.js');
require('./builders/log/log.controller.js');
require('./builders/log/log.route.js');
require('./builders/log/logviewer/logpreview.directive.js');
require('./builders/log/logviewer/logviewer.directive.js');
require('./builders/log/logviewer/scrollviewport.directive.js');
require('./builders/services/findbuilds.factory.js');
require('./builders/services/timeout.factory.js');
require('./builders/step/step.controller.js');
require('./builders/step/step.route.js');
require('./buildrequests/pendingbuildrequests.controller.js');
require('./buildrequests/pendingbuildrequests.route.js');
require('./changes/changebuilds/changebuilds.controller.js');
require('./changes/changebuilds/changebuilds.route.js');
require('./changes/changes.controller.js');
require('./changes/changes.route.js');
require('./common/common.constant.js');
require('./common/directives/basefield/basefield.directive.js');
require('./common/directives/buildrequestsummary/buildrequestsummary.directive.js');
require('./common/directives/builds/buildstable.directive.js');
require('./common/directives/buildsticker/buildsticker.directive.js');
require('./common/directives/buildsummary/buildsummary.directive.js');
require('./common/directives/changedetails/changedetails.directive.js');
require('./common/directives/changelist/changelist.directive.js');
require('./common/directives/connectionstatus/connectionstatus.directive.js');
require('./common/directives/forcefields/forcefields.directive.js');
require('./common/directives/lineplot/lineplot.directive.js');
require('./common/directives/loginbar/loginbar.directive.js');
require('./common/directives/properties/properties.directive.js');
require('./common/directives/rawdata/rawdata.directive.js');
require('./common/directives/windowtitle/windowtitle.directive.js');
require('./common/filters/moment/moment.constant.js');
require('./common/filters/moment/moment.filter.js');
require('./common/filters/publicFields.filter.js');
require('./common/services/ansicodes/ansicodes.service.js');
require('./common/services/buildercache/buildercache.service.js');
require('./common/services/datagrouper/datagrouper.service.js');
require('./common/services/favicon/favicon.service.js');
require('./common/services/results/results.service.js');
require('./common/services/settings/settings.service.js');
require('./d3/d3.service.js');
require('./home/home.controller.js');
require('./home/home.route.js');
require('./masters/master/master.route.js');
require('./masters/masters.controller.js');
require('./masters/masters.route.js');
require('./schedulers/schedulers.controller.js');
require('./schedulers/schedulers.route.js');
require('./settings/settings.controller.js');
require('./settings/settings.route.js');
require('./workers/worker/worker.route.js');
require('./workers/workeraction.dialog.js');
require('./workers/workers.controller.js');
require('./workers/workers.route.js');
require('../img/favicon.ico');
require('../img/icon.png');
require('../img/icon.svg');
require('../img/icon16.svg');
require('../img/nobody.png');

import 'angular-animate';
import 'angular-ui-bootstrap';
import 'lodash';
import '@uirouter/angularjs';

if (window.T === undefined){
    window.T = {}
}
angular.module("guanlecoja.ui", ["ui.bootstrap", "ui.router", "ngAnimate"]);

require('./breadcrumb_service/breadcrumb.service.js');
require('./menu_service/menu.service.js');
require('./notification_service/httpinterceptor.js');
require('./notification_service/notification.service.js');
require('./notification_widget/notification.directive.js');
require('./page_with_sidebar/page_with_sidebar.directive.js');
require('./topbar-contextual-actions/topbar-contextual-actions.directive.js');
require('./topbar/topbar.directive.js');


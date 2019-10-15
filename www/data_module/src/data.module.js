angular.module('bbData', []);

require('./classes/base.service.js');
require('./classes/builder.service.js');
require('./classes/buildrequest.service.js');
require('./classes/build.service.js');
require('./classes/buildset.service.js');
require('./classes/change.service.js');
require('./classes/changesource.service.js');
require('./classes/forcescheduler.service.js');
require('./classes/logs.service.js');
require('./classes/master.service.js');
require('./classes/properties.service.js');
require('./classes/scheduler.service.js');
require('./classes/sourcestamp.service.js');
require('./classes/step.service.js');
require('./classes/worker.service.js');
require('./data.constant.js');
require('./services/data/collection/collection.service.js');
require('./services/data/collection/dataquery.service.js');
require('./services/data/data.service.js');
require('./services/dataUtils/dataUtils.service.js');
require('./services/rest/rest.service.js');
require('./services/socket/socket.service.js');
require('./services/socket/webSocketBackend.service.js');
require('./services/socket/websocket.service.js');
require('./services/stream/stream.service.js');


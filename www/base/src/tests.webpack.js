// This file is an entry point for angular tests
// Avoids some weird issues when using webpack + angular.

import 'angular';
import 'angular-mocks/angular-mocks';
import './app/app.module.js'
import '../test/scripts/mocks/config.mock.js'

const context = require.context('./', true, /\.spec.js$/);
context.keys().forEach(context);

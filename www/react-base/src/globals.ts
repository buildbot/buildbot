// Vite seems not to have functionality to provide globals for embedded libraries, so this is done
// here manually.

import axios from 'axios';
import * as mobx from 'mobx';
import moment from 'moment';
import React from 'react';
import ReactDOM from 'react-dom/client';
import * as ReactRouterDOM from 'react-router-dom';
import * as jquery from 'jquery';

declare global {
  var axios: any;
  var mobx: any;
  var React: any;
  var ReactRouterDOM: any;
  var jQuery: any;
  var $: any;
}

window.axios = axios;
window.mobx = mobx;
window.moment = moment;
window.React = React;
window.ReactDOM = ReactDOM as any;
window.ReactRouterDOM = ReactRouterDOM;
window.jQuery = jquery;
window.$ = jquery;

// Vite seems not to have functionality to provide globals for embedded libraries, so this is done
// here manually.

import axios from 'axios';
import * as mobx from 'mobx';
import * as mobxReact from 'mobx-react';
import moment from 'moment';
import React from 'react';
import ReactDOM from 'react-dom';
import * as ReactRouterDOM from 'react-router-dom';
import * as jquery from 'jquery';
import * as BuildbotPluginSupport from 'buildbot-plugin-support';

declare global {
  interface Window {
    axios: any;
    mobx: any;
    mobxReact: any;
    React: any;
    ReactRouterDOM: any;
    jQuery: any;
    $: any;
    BuildbotPluginSupport: any;
  }
}

window.axios = axios;
window.mobx = mobx;
window.mobxReact = mobxReact;
window.moment = moment;
window.React = React;
window.ReactDOM = ReactDOM as any;
window.ReactRouterDOM = ReactRouterDOM;
window.jQuery = jquery;
window.$ = jquery;
window.BuildbotPluginSupport = BuildbotPluginSupport;

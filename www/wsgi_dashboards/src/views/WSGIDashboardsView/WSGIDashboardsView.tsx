/*
  This file is part of Buildbot.  Buildbot is free software: you can
  redistribute it and/or modify it under the terms of the GNU General Public
  License as published by the Free Software Foundation, version 2.

  This program is distributed in the hope that it will be useful, but WITHOUT
  ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
  FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
  details.

  You should have received a copy of the GNU General Public License along with
  this program; if not, write to the Free Software Foundation, Inc., 51
  Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

  Copyright Buildbot Team Members
*/

import axios, {AxiosRequestConfig} from 'axios';
import {createElement, useEffect, useRef, useState} from "react";
import * as fa from "react-icons/fa";
import {CancellablePromise, capitalize} from "buildbot-data-js";
import {LoadingIndicator} from "buildbot-ui";
import {buildbotSetupPlugin} from "buildbot-plugin-support";

function getWsgiUrl(location: Location, name) {
  let pathname = location.pathname;
  if (!pathname.endsWith("/")) {
    pathname += "/";
  }
  return `${location.protocol}//${location.hostname}:${location.port}${pathname}plugins/wsgi_dashboards/${name}/index.html`;
}

function getData(url) {
  return new CancellablePromise<any>((resolve, reject, onCancel) => {
    const controller = new AbortController();
    onCancel(() => {
      controller.abort();
    });
    let config = {
      method: 'get',
      url,
      params: {},
      signal: controller.signal,
    };
    const request = axios.request(config);
    request.then(response => {
      resolve(response.data);
    }).catch(reason => {
      reject(reason);
    })
  });
}

export default function WSGIDashboardsView({ name }) {
  const location = getWsgiUrl(window.location, name);
  const pendingRequest = useRef<CancellablePromise<any> | null>(null);

  const [wsgiContent, setWsgiContent] = useState(undefined);

  useEffect(() => {
    if (pendingRequest.current !== null) {
      pendingRequest.current.cancel();
    }

    pendingRequest.current = getData(location);
    pendingRequest.current.then(content => {
      setWsgiContent(content);
    });
    return () => {
      if (pendingRequest.current !== null) {
        pendingRequest.current.cancel();
      }
    };
  }, [location]);

  if (wsgiContent === undefined) {
    return  (
      <div className="bb-wsgi-dashboard-view container">
        <LoadingIndicator/>
      </div>
    )
  }
  return (
    <div className="bb-wsgi-dashboard-view container" dangerouslySetInnerHTML={{__html: wsgiContent}} />
  )
}

buildbotSetupPlugin((reg, config) => {
  const wsgi_dashboards = config.plugins['wsgi_dashboards'];

  for (let dashboard of wsgi_dashboards) {
    const { name } = dashboard;
    let { caption } = dashboard;
    if (caption == null) { caption = capitalize(name); }
    if (dashboard.order == null) { dashboard.order = 5; }

    const icon = fa['Fa' + capitalize(dashboard.icon)];

    reg.registerMenuGroup({
      name: name,
      caption: caption,
      icon: createElement(icon, {}),
      order: dashboard.order,
      route: `/wsgi/${name}`,
      parentName: null,
    });
  
    reg.registerRoute({
      route: `/wsgi/${name}`,
      group: name,
      element: () => <WSGIDashboardsView name={name}/>,
    });
  }
});


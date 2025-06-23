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
import {createElement, useEffect, useRef, useState} from 'react';
import * as fa from 'react-icons/fa';
import {IconType} from 'react-icons';
import {CancellablePromise, capitalize} from 'buildbot-data-js';
import {LoadingIndicator} from 'buildbot-ui';
import {buildbotSetupPlugin} from 'buildbot-plugin-support';
import {FaExclamationCircle} from 'react-icons/fa';

function getWsgiUrl(location: Location, name: string) {
  let pathname = location.pathname;
  if (!pathname.endsWith('/')) {
    pathname += '/';
  }
  return `${location.protocol}//${location.hostname}:${location.port}${pathname}plugins/wsgi_dashboards/${name}/index.html`;
}

function getData(url: string) {
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
    request
      .then((response) => {
        resolve(response.data);
      })
      .catch((reason) => {
        reject(reason);
      });
  });
}

export type WSGIDashboardsViewProps = {
  name: string;
};

export default function WSGIDashboardsView({name}: WSGIDashboardsViewProps) {
  const location = getWsgiUrl(window.location, name);
  const pendingRequest = useRef<CancellablePromise<any> | null>(null);

  const [wsgiContent, setWsgiContent] = useState(undefined);

  useEffect(() => {
    if (pendingRequest.current !== null) {
      pendingRequest.current.cancel();
    }

    pendingRequest.current = getData(location);
    pendingRequest.current.then((content) => {
      setWsgiContent(content);
    });
    return () => {
      if (pendingRequest.current !== null) {
        pendingRequest.current.cancel();
      }
    };
  }, [location]);

  if (wsgiContent === undefined) {
    return (
      <div className="bb-wsgi-dashboard-view container">
        <LoadingIndicator />
      </div>
    );
  }
  return (
    <div
      className="bb-wsgi-dashboard-view container"
      dangerouslySetInnerHTML={{__html: wsgiContent}}
    />
  );
}

function getIcon(iconNames: string[]): IconType | undefined {
  for (const iconName in iconNames) {
    // @ts-ignore
    const icon = fa[iconName];
    if (icon !== undefined) {
      return icon;
    }
  }
  return undefined;
}

buildbotSetupPlugin((reg, config) => {
  const wsgi_dashboards = config.plugins['wsgi_dashboards'];

  for (let dashboard of wsgi_dashboards) {
    const {name} = dashboard;
    let {caption} = dashboard;
    if (caption == null) {
      caption = capitalize(name);
    }
    if (dashboard.order == null) {
      dashboard.order = 5;
    }

    const iconNames = ['Fa' + capitalize(dashboard.icon), String(dashboard.icon)];

    let icon = getIcon(iconNames);
    if (icon === undefined) {
      icon = FaExclamationCircle;
      console.log(`Error in WSGI plugin ${name}: Could not find icon ${dashboard.icon}`);
    }

    reg.registerMenuGroup({
      name: name,
      caption: caption,
      icon: createElement(icon, {}),
      order: dashboard.order,
      route: `/${name}`,
      parentName: null,
    });

    reg.registerRoute({
      route: `/${name}`,
      group: name,
      element: () => <WSGIDashboardsView name={name} />,
    });
  }
});

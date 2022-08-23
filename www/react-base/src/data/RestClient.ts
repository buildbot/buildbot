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
import {CancellablePromise} from "../util/CancellablePromise";

export default class RestClient {
  rootUrl: string;

  constructor(rootUrl: string) {
    this.rootUrl = rootUrl;
    if (!this.rootUrl.endsWith("/")) {
      this.rootUrl += "/";
    }
  }

  private buildCancellablePromise(config: AxiosRequestConfig) {
    return new CancellablePromise<any>((resolve, reject, onCancel) => {
      const controller = new AbortController();
      onCancel(() => {
        controller.abort();
      });
      config.signal = controller.signal;
      const request = axios.request(config);
      request.then(response => {
        resolve(response.data);
      }).catch(reason => {
        reject(reason);
      })
    });
  }

  get(url: string, params?: {[key: string]: string}) {
    if (params === undefined) {
      params = {};
    }
    return this.buildCancellablePromise({
      method: 'get',
      url: this.rootUrl + url,
      params: params
    });
  }

  del(url: string) {
    return this.buildCancellablePromise({
      method: 'delete',
      url: this.rootUrl + url
    });
  }

  put(url: string, body: object) {
    return this.buildCancellablePromise({
      method: 'put',
      url: this.rootUrl + url,
      data: body,
    });
  }

  post(url: string, body: object) {
    return this.buildCancellablePromise({
      method: 'post',
      url: this.rootUrl + url,
      data: body,
    });
  }
}

export function getRestUrl(location: Location) {
  return `${location.protocol}//${location.hostname}:${location.port}/api/v2`;
}
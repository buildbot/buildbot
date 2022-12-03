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

// Axios 1.0.0 will provide an easier way to disable emission of braces, for now we use a modified
// version of Axios internal serializer as of 0.27.2. The following three functions are:
// # Copyright (c) 2014-present Matt Zabriskie & Collaborators
//
// Permission is hereby granted, free of charge, to any person obtaining a copy of this software
// and associated documentation files (the "Software"), to deal in the Software without restriction,
// including without limitation the rights to use, copy, modify, merge, publish, distribute,
// sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:
//
// The above copyright notice and this permission notice shall be included in all copies or
// substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
// BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
// NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
// DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
const axiosEncode = (val: any) => {
  return encodeURIComponent(val)
    .replace(/%3A/gi, ':')
    .replace(/%24/g, '$')
    .replace(/%2C/gi, ',')
    .replace(/%20/g, '+')
    .replace(/%5B/gi, '[')
    .replace(/%5D/gi, ']');
}

const axiosForEach = (obj: any, fn: (obj: any, key: any) => void) => {
  // Don't bother if no value provided
  if (obj === null || typeof obj === 'undefined') {
    return;
  }

  // Force an array if not already something iterable
  if (typeof obj !== 'object') {
    /*eslint no-param-reassign:0*/
    obj = [obj];
  }

  if (Array.isArray(obj)) {
    // Iterate over array values
    for (let i = 0, l = obj.length; i < l; i++) {
      fn(obj[i], i);
    }
  } else {
    // Iterate over object keys
    const keys = Object.keys(obj);
    const len = keys.length;
    let key;

    for (let i = 0; i < len; i++) {
      key = keys[i];
      fn(obj[key], key);
    }
  }
}

const axiosParamsSerializerWithoutBraces = (params: any[]) => {
  let parts: string[] = [];

  axiosForEach(params, (val, key) => {
    if (val === null || typeof val === 'undefined') {
      return;
    }

    if (!Array.isArray(val)) {
      val = [val];
    }

    axiosForEach(val, (v: any) => {
      if (v !== null && typeof v === 'object') {
        v = JSON.stringify(v);
      }
      parts.push(axiosEncode(key) + '=' + axiosEncode(v));
    });
  });

  return parts.join('&');
}

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
      params: params,
      paramsSerializer: axiosParamsSerializerWithoutBraces,
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

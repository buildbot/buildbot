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

import {Stream} from "../util/Stream";

export type PromiseData<T> = {
  promise: Promise<T> | null;
  resolve: (value: T | PromiseLike<T>) => void;
  reject: (reason?: any) => void;
};

export class WebSocketClient {
  url: string;
  socket: WebSocket;
  queue: any[] = [];
  eventStream: Stream<any> = new Stream();
  promises: {[id: string]: PromiseData<void>} = {};
  subscribers: {[path: string]: any} = {};
  lastId: number = 0;

  constructor(url: string, websocketProvider: (url: string) => WebSocket) {
    this.url = url;

    this.socket = websocketProvider(this.url);
    this.socket.onopen = this.onOpen;
    this.socket.onmessage = this.onMessage;
  }

  onOpen = (ev: Event) => {
    this.flush();
  }

  onMessage = (ev: MessageEvent) => {
    const data = JSON.parse(ev.data);

    // response message
    if (data.code !== null && data.code !== undefined) {
      const id: string = data._id;
      if (id in this.promises) {
        const promise = this.promises[id];
        if (data.code === 200) {
          promise.resolve();
        } else {
          promise.reject(new Error(data));
        }
      }
    } else {
      // status update message
      setTimeout(() => this.eventStream.push(data), 0);
    }
  }

  /* sends data via the websocket message.
     Returns a promise, which will be resolved once a response message with the same id has been
     received has the same id
  */
  send(data: any) {
    // add _id to each message
    const id = this.generateId();
    data._id = id;

    const promiseData = {} as PromiseData<void>;
    promiseData.promise = new Promise<void>((resolve, reject) => {
      promiseData.resolve = resolve;
      promiseData.reject = reject;
    });
    this.promises[id] = promiseData;

    const jsonData = JSON.stringify(data);
    if (this.socket.readyState === this.socket.OPEN) {
      this.socket.send(jsonData);
    } else {
      // if the WebSocket is not open yet, add the data to the queue
      this.queue.push(jsonData);
    }
    // socket is not watched by cypress, so we need to
    // create a timeout while we are using the socket so that protractor waits for it
    const to = setTimeout(() => {}, 20000);

    return promiseData.promise.then(() => {
      clearTimeout(to);
    });
  }

  flush() {
    // send all the data waiting in the queue
    let data;
    while ((data = this.queue.pop())) {
      this.socket.send(data);
    }
  }

  generateId() {
    this.lastId = this.lastId + 1;
    return this.lastId;
  }

  // High level api. Maintain a list of subscribers for one event path
  subscribe(eventPath: string, subscriber: any) {
    const subscribersForPath = this.getSubscribersList(eventPath);
    subscribersForPath.push(subscriber);
    if (subscribersForPath.length === 1) {
      return this.send({
        cmd: "startConsuming",
        path: eventPath
      });
    }
    return Promise.resolve();
  }

  unsubscribe(eventPath: string, collection: any) {
    const subscribersForPath = this.getSubscribersList(eventPath);
    const pos = subscribersForPath.indexOf(collection);
    if (pos >= 0) {
      subscribersForPath.splice(pos, 1);
      if (subscribersForPath.length === 0) {
        return this.send({
          cmd: "stopConsuming",
          path: eventPath
        });
      }
    }
    return Promise.resolve();
  }

  private getSubscribersList(eventPath: string) {
    if (!(eventPath in this.subscribers)) {
      this.subscribers[eventPath] = [];
    }
    return this.subscribers[eventPath];
  }
}

export function getWebSocketUrl(location: Location) {
  const hostname = location.hostname;
  const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
  const defaultport = location.protocol === 'https:' ? '443' : '80';
  const path = location.pathname;
  const port = location.port === defaultport ? '' : `:${location.port}`;
  return `${protocol}://${hostname}${port}${path}ws`;
}

/*
  This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the
  MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.

  Copyright Buildbot Team Members
*/

import {action, makeObservable, observable} from "mobx";
import {DataQuery, Query} from "./DataQuery";
import {IDataAccessor} from "./DataAccessor";
import {WebSocketClient} from "./WebSocketClient";
import {endpointPath, socketPath, socketPathRE} from "./DataUtils";
import {IDataCollection} from "./DataCollection";

export class DataPropertiesCollection implements IDataCollection {
  restPath!: string;
  query!: Query;
  accessor!: IDataAccessor;
  socketPath!: string;
  endpoint!: string;
  socketPathRE!: RegExp;
  queryExecutor!: DataQuery;
  webSocketClient!: WebSocketClient;
  isOpen: boolean = false;

  @observable resolved: boolean = false;
  @observable properties = observable.map<string, any>();

  constructor() {
    makeObservable(this);
  }

  get(key: string) {
    return this.properties.get(key);
  }

  has(key: string) {
    return this.properties.has(key);
  }

  @action listener(data: any) {
    const key = data.k;
    const message = data.m;
    // Test if the message is for me
    if (this.socketPathRE.test(key)) {
      // Property updates contain only updated or new properties
      for (const key in message) {
        this.properties.set(key, message[key]);
      }
    }
  }

  isValid() {
    if (this.accessor === undefined) {
      return false;
    }
    return this.accessor.isOpen();
  }

  isResolved() {
    return this.resolved;
  }

  subscribe() {
    return this.webSocketClient.subscribe(this.socketPath, this);
  }

  open(restPath: string, query: Query, accessor: IDataAccessor,
       webSocketClient: WebSocketClient) {
    this.restPath = restPath;
    this.query = query;
    this.accessor = accessor;
    this.webSocketClient = webSocketClient;
    this.socketPath = socketPath(this.restPath);
    this.endpoint = endpointPath(this.restPath);
    this.socketPathRE = socketPathRE(this.socketPath);
    this.queryExecutor = new DataQuery(this.query);

    webSocketClient.eventStream.subscribe(this.listener.bind(this));
    this.accessor.registerCollection(this);
    this.isOpen = true;
  }

  close() {
    if (this.isOpen) {
      this.isOpen = false;
      this.accessor.unregisterCollection(this);
      return this.webSocketClient.unsubscribe(this.socketPath, this);
    }
    return Promise.resolve();
  }

  @action initial(data: any[]) {
    // Properties always contain the key-value object as a first item in the array
    this.properties.replace(data.length > 0 ? data[0] : {});
    this.resolved = true;
  }

  @action clear() {
    this.properties.replace({});
  }
}

/*
  This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the
  MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.

  Copyright Buildbot Team Members
*/

import {DataQuery, Query} from "./DataQuery";
import {endpointPath, socketPath, socketPathRE} from "./DataUtils";
import {WebSocketClient} from "./WebSocketClient";
import {BaseClass} from "./classes/BaseClass";
import {IDataDescriptor} from "./classes/DataDescriptor";
import {IDataAccessor} from "./DataAccessor";
import {action, IObservableArray, makeObservable, observable} from "mobx";
import {DataMultiCollection} from "./DataMultiCollection";
import {DataPropertiesCollection} from "./DataPropertiesCollection";
import {DataMultiPropertiesCollection} from "./DataMultiPropertiesCollection";

export interface IDataCollection {
  // A valid data collection is one that listens to data changes from the API. The initial set of data objects may
  // not have been acquired yet, isResolved() tracks this. Invalid data collections are the ones that are constructed
  // without an accessor and the ones whose accessor has expired.
  isValid(): boolean;
  isResolved(): boolean;
  subscribe(): Promise<void>;
  initial(data: any[]): void;
  close(): Promise<void>;
}

export class DataCollection<DataType extends BaseClass> implements IDataCollection {
  restPath!: string;
  query!: Query;
  accessor!: IDataAccessor;
  socketPath!: string;
  endpoint!: string;
  socketPathRE!: RegExp;
  queryExecutor!: DataQuery;
  descriptor!: IDataDescriptor<DataType>;
  webSocketClient!: WebSocketClient;
  isOpen: boolean = false;
  internalId: number = 0;

  @observable resolved: boolean = false;
  @observable array: IObservableArray<DataType> = observable<DataType>([]);
  @observable byId: {[key: string]: DataType} = {};

  constructor(internalId: number = 0) {
    makeObservable(this);
    this.internalId = internalId;
  }

  listener(data: any) {
    const key = data.k;
    const message = data.m;
    // Test if the message is for me
    if (this.socketPathRE.test(key)) {
      this.put(message);
      this.recomputeQuery();
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
       descriptor: IDataDescriptor<DataType>, webSocketClient: WebSocketClient) {
    this.restPath = restPath;
    this.query = query;
    this.accessor = accessor;
    this.webSocketClient = webSocketClient;
    this.socketPath = socketPath(this.restPath);
    this.endpoint = endpointPath(this.restPath);
    this.socketPathRE = socketPathRE(this.socketPath);
    this.queryExecutor = new DataQuery(this.query);
    this.descriptor = descriptor;

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

  getRelated<ChildDataType extends BaseClass>(
      callback: (parent: DataType) => DataCollection<ChildDataType>) {
    return new DataMultiCollection<DataType, ChildDataType>(this.accessor, this.array, null, null,
      callback);
  }

  getRelatedProperties(callback: (child: DataType) => DataPropertiesCollection) {
    return new DataMultiPropertiesCollection<DataType>(this.accessor, this.array, null, null,
      callback);
  }

  getRelatedOfFiltered<ChildDataType extends BaseClass>(
      filteredIds: IObservableArray<string>,
      callback: (child: DataType) => DataCollection<ChildDataType>) {
    return new DataMultiCollection<DataType, ChildDataType>(this.accessor, this.array, null,
      filteredIds, callback);
  }

  getNthOrNull(index: number): DataType | null {
    if (index >= this.array.length) {
      return null;
    }
    return this.array[index];
  }

  getByIdOrNull(id: string): DataType | null {
    if (id in this.byId) {
      return this.byId[id];
    }
    return null;
  }

  @action initial(data: any[]) {
    // put items one by one if not already in the array if they are that means they come from an
    // update event the event is always considered the latest data so we don't overwrite it
    // with REST data
    for (const element of data) {
      const id = element[this.descriptor.fieldId];
      if (!(id in this.byId)) {
        this.put(element);
      }
    }
    this.resolved = true;
    this.recomputeQuery();
  }

  @action from(data: any[]) {
    // put items one by one
    for (let element of data) {
      this.put(element);
    }
    this.recomputeQuery();
  }

  @action add(element: any) {
    // don't create wrapper if element is filtered
    if (this.queryExecutor.filter([element]).length === 0) {
      return;
    }
    const instance = this.descriptor.parse(this.accessor, this.endpoint, element);
    this.byId[instance.id] = instance;
    this.array.push(instance);
  }

  @action put(element: any) {
    const id = element[this.descriptor.fieldId];
    if (id in this.byId) {
      const old = this.byId[id];
      old.update(element);
      return;
    }

    // if not found, add it.
    this.add(element);
  }

  @action clear() {
    this.array.replace([]);
  }

  @action delete(element: DataType) {
    const index = this.array.indexOf(element);
    if (index > -1) {
      this.array.splice(index, 1);
    }
  }

  @action recomputeQuery() {
    this.queryExecutor.computeQuery(this.array);
  }
}

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
import {action, IObservableArray, ObservableMap, makeObservable, observable} from "mobx";
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
  // does not contain elements that have been filtered out and off limits
  @observable array: IObservableArray<DataType> = observable<DataType>([]);
  // does not contain elements that have been filtered out
  @observable byId: ObservableMap<string, DataType> = observable.map<string, DataType>();

  // includes IDs of all elements received before resolved becomes true. This is necessary to
  // track which elements have been received, but filtered out.
  idsBeforeResolve = new Set<string>();

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
    return this.byId.get(id) ?? null;
  }

  @action initial(data: any[]) {
    // put items one by one if not already in the array if they are that means they come from an
    // update event the event is always considered the latest data so we don't overwrite it
    // with REST data
    for (const element of data) {
      const id = element[this.descriptor.fieldId];
      if (!this.idsBeforeResolve.has(String(id))) {
        this.put(element);
      }
    }
    this.resolved = true;
    this.idsBeforeResolve.clear();
    this.recomputeQuery();
  }

  @action put(element: any) {
    const id = element[this.descriptor.fieldId];
    if (!this.resolved) {
      this.idsBeforeResolve.add(String(id));
    }

    const old = this.byId.get(String(id));
    if (old !== undefined) {
      if (!this.queryExecutor.isAllowedByFilters(element)) {
        // existing item, but updated data has property that filters out the element outright
        if (this.queryExecutor.limit !== null &&
          this.array.length === this.queryExecutor.limit &&
          this.byId.size > this.array.length)
        {
          // Array was limited, however there are more up-to-date data in byId that can be filled
          // in.
          this.byId.delete(String(id));
          this.array.replace([...this.byId.values()]);
          this.recomputeQuery();
        } else {
          this.byId.delete(String(id));
          this.deleteFromArray(old);
        }
        return;
      }
      // update items that are not filtered out
      old.update(element);
      return;
    }

    if (!this.queryExecutor.isAllowedByFilters(element)) {
      // ignore items that are filtered out
      return;
    }

    // add items that are not filtered out
    const instance = this.descriptor.parse(this.accessor, this.endpoint, element);
    this.byId.set(instance.id, instance);
    this.array.push(instance);
  }

  @action clear() {
    this.array.replace([]);
  }

  @action deleteFromArray(element: DataType) {
    const index = this.array.indexOf(element);
    if (index > -1) {
      this.array.splice(index, 1);
    }
  }

  @action recomputeQuery() {
    this.queryExecutor.applySort(this.array);
    this.queryExecutor.applyLimit(this.array);
  }
}

/*
  This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the
  MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.

  Copyright Buildbot Team Members
*/

import {DataCollection, IDataCollection} from "./DataCollection";
import {DataClient} from "./DataClient";
import {IDataDescriptor} from "./classes/DataDescriptor";
import {ControlParams, Query, RequestQuery} from "./DataQuery";
import {BaseClass} from "./classes/BaseClass";
import {DataPropertiesCollection} from "./DataPropertiesCollection";
import {CancellablePromise} from "../util/CancellablePromise";

export interface IDataAccessor {
  registerCollection(c: IDataCollection): void;
  unregisterCollection(c: IDataCollection): void;
  isOpen(): boolean;
  close(): void;
  get<DataType extends BaseClass>(endpoint: string, query: RequestQuery,
                                  descriptor: IDataDescriptor<DataType>): DataCollection<DataType>;
  getProperties(endpoint: string, query: RequestQuery): DataPropertiesCollection;

  getRaw(endpoint: string, query: Query): CancellablePromise<any>;
  control(endpoint: string, method: string, params: ControlParams): Promise<any>;
}

export class BaseDataAccessor implements IDataAccessor {
  private registeredCollections: IDataCollection[] = [];
  private client: DataClient;
  private _isOpen: boolean = true;

  constructor(client: DataClient) {
    this.client = client;
  }

  registerCollection(c: IDataCollection) {
    this.registeredCollections.push(c);
  }

  unregisterCollection(c: IDataCollection) {
    const index = this.registeredCollections.indexOf(c);
    if (index >= 0) {
      this.registeredCollections.splice(index, 1);
    }
  }

  isOpen() { return this._isOpen; }

  close() {
    this._isOpen = false;
    // We take a copy because collections will remove themselves from the
    // registeredCollections array
    for (const c of [...this.registeredCollections]) {
      c.close();
    }
  }

  get<DataType extends BaseClass>(endpoint: string, query: RequestQuery,
                                  descriptor: IDataDescriptor<DataType>): DataCollection<DataType> {
    if (query.id !== undefined) {
      endpoint += "/" + query.id;
    }
    return this.client.get(endpoint, this, descriptor, query.query ?? {}, query.subscribe ?? true);
  }

  getProperties(endpoint: string, query: RequestQuery): DataPropertiesCollection {
    if (query.id !== undefined) {
      endpoint += "/" + query.id;
    }
    return this.client.getProperties(endpoint, this, query.query ?? {}, query.subscribe ?? true);
  }

  getRaw(endpoint: string, query: Query): CancellablePromise<any> {
    return this.client.restClient.get(endpoint, query);
  }

  control(endpoint: string, method: string, params: ControlParams) {
    return this.client.control(endpoint, method, params);
  }
}

export class EmptyDataAccessor implements IDataAccessor {
  registerCollection(c: IDataCollection) {}
  unregisterCollection(c: IDataCollection) {}

  isOpen() { return false; }
  close() {}

  get<DataType extends BaseClass>(endpoint: string, query: RequestQuery,
                                  descriptor: IDataDescriptor<DataType>): DataCollection<DataType> {
    throw Error("Not implemented");
  }

  getProperties(endpoint: string, query: RequestQuery): DataPropertiesCollection {
    throw Error("Not implemented");
  }

  getRaw(endpoint: string, query: Query): CancellablePromise<any> {
    throw Error("Not implemented");
  }

  control(endpoint: string, method: string, params: ControlParams): Promise<any> {
    throw Error("Not implemented");
  }
}

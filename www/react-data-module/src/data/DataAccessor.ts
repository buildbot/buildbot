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

import DataCollection, {IDataCollection} from "./DataCollection";
import DataClient from "./DataClient";
import IDataDescriptor from "./classes/DataDescriptor";
import {ControlParams, Query, RequestQuery} from "./DataQuery";
import BaseClass from "./classes/BaseClass";
import DataPropertiesCollection from "./DataPropertiesCollection";
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

export default class BaseDataAccessor implements IDataAccessor {
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

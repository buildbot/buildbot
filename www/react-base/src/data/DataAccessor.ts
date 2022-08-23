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
import {RequestQuery} from "./DataQuery";
import BaseClass from "./classes/BaseClass";

export interface IDataAccessor {
  registerCollection(c: IDataCollection): void;
  unregisterCollection(c: IDataCollection): void;
  close(): void;
  get<DataType extends BaseClass>(endpoint: string, query: RequestQuery,
                                  descriptor: IDataDescriptor<DataType>): DataCollection<DataType>;
}

export default class BaseDataAccessor implements IDataAccessor {
  private registeredCollections: IDataCollection[] = [];
  private client: DataClient;

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

  close() {
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
}

export class EmptyDataAccessor implements IDataAccessor {
  registerCollection(c: IDataCollection) {}
  unregisterCollection(c: IDataCollection) {}

  close() {}

  get<DataType extends BaseClass>(endpoint: string, query: RequestQuery,
                                  descriptor: IDataDescriptor<DataType>): DataCollection<DataType> {
    throw Error("Not implemented");
  }
}
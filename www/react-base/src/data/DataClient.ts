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

import RestClient from "./RestClient";
import {WebSocketClient} from "./WebSocketClient";
import BaseDataAccessor, {IDataAccessor} from "./DataAccessor";
import {ControlParams, Query} from "./DataQuery";
import DataCollection, {IDataCollection} from "./DataCollection";
import IDataDescriptor, {IAnyDataDescriptor} from "./classes/DataDescriptor";
import BaseClass from "./classes/BaseClass";
import DataPropertiesCollection from "./DataPropertiesCollection";
import {propertiesDescriptor} from "./classes/Properties";

export default class DataClient {
  restClient: RestClient;
  webSocketClient: WebSocketClient;
  private jsonRpcId: number = 1;

  constructor(restClient: RestClient, webSocketClient: WebSocketClient) {
    this.restClient = restClient;
    this.webSocketClient = webSocketClient;
  }

  get<DataType extends BaseClass>(endpoint: string, accessor: IDataAccessor,
                                  descriptor: IDataDescriptor<DataType>,
                                  query: Query, subscribe: boolean) {
    return this.getAny(endpoint, accessor, descriptor, query, subscribe,
      () => {
        const c = new DataCollection<DataType>();
        c.open(endpoint, query, accessor, descriptor, this.webSocketClient);
        return c;
      });
  }

  getProperties(endpoint: string, accessor: IDataAccessor,
                query: Query, subscribe: boolean) {
    return this.getAny(endpoint, accessor, propertiesDescriptor, query, subscribe,
      () => {
        const c = new DataPropertiesCollection();
        c.open(endpoint, query, accessor, this.webSocketClient);
        return c;
      });
  }

  getAny<T extends IDataCollection>(endpoint: string, accessor: IDataAccessor,
                                    descriptor: IAnyDataDescriptor, query: Query,
                                    subscribe: boolean, collectionFactory: () => T) {
    // subscribe for changes if 'subscribe' is true
    if (subscribe && !accessor) {
      console.warn("subscribe call should be done after DataClient.open() for " +
        "maintaining trace of observers");
      subscribe = false;
    }

    const collection = collectionFactory();

    const subscribePromise = subscribe ? collection.subscribe() : Promise.resolve();

    subscribePromise.then(() =>
      // get the data from the rest api
      this.restClient.get(endpoint, query).then((response) => {
        const datalist = response[descriptor.restArrayField];
        // the response should always be an array
        if (!Array.isArray(datalist)) {
          console.error(`${datalist} is not an array when retrieving ${descriptor.restArrayField}`);
          return;
        }

        // fill up the collection with initial data
        collection.initial(datalist);
      })
    );

    return collection;
  }

  control(endpoint: string, method: string, params: ControlParams) {
    return this.restClient.post(endpoint, {
        id: this.getNextRpcId(),
        jsonrpc: '2.0',
        method,
        params
      }
    );
  }

  private getNextRpcId() {
    return this.jsonRpcId++;
  }

  // opens a new accessor
  open() {
    return new BaseDataAccessor(this);
  }
}

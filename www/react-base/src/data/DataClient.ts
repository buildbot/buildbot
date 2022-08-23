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
import {restPath} from "./DataUtils";
import BaseDataAccessor, {IDataAccessor} from "./DataAccessor";
import {Query} from "./DataQuery";
import DataCollection from "./DataCollection";
import IDataDescriptor from "./classes/DataDescriptor";
import BaseClass from "./classes/BaseClass";

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
    // subscribe for changes if 'subscribe' is true
    if (subscribe && !accessor) {
      console.warn("subscribe call should be done after DataClient.open() for " +
        "maintaining trace of observers");
      subscribe = false;
    }

    // up to date array, this will be returned
    const collection = new DataCollection<DataType>();
    collection.open(endpoint, query, accessor, descriptor, this.webSocketClient);

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

  control(endpoint: string, id: string, method: string, params?: {[key: string]: string}) {
    if (params === undefined) {
      params = {};
    }
    return this.restClient.post(restPath([endpoint, id]), {
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

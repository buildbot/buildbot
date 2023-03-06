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

import DataClient from "./DataClient";
import {Query} from "./DataQuery";
import BaseClass from "./classes/BaseClass";
import BaseDataAccessor from "./DataAccessor";
import IDataDescriptor from "./classes/DataDescriptor";
import DataCollection from "./DataCollection";
import {restPath} from "./DataUtils";

type MockedResult = {
  endpoint: string;
  query: Query;
  returnValue: any;
}

export default class MockDataClient extends DataClient {
  private isSpied: boolean = false;
  private mocks: MockedResult[] = [];
  private expects: {endpoint: string, query: Query}[] = [];

  when(endpoint: string, query: Query, returnValue: any) {
    for (const mock of this.mocks) {
      if (mock.endpoint === endpoint && mock.query === query) {
        mock.returnValue = returnValue;
        return;
      }
    }

    this.mocks.push({endpoint: endpoint, query: query, returnValue: returnValue});
  }

  expect(endpoint: string, query: Query, returnValue: any) {
    this.expects.push({endpoint: endpoint, query: query});
    return this.when(endpoint, query, returnValue);
  }

  verifyNoOutstandingExpectation() {
    if (this.expects.length) {
      fail(`expecting ${this.expects.length} more data requests ` +
        `(${JSON.stringify(this.expects)})`);
    }
  }

  // register return values with the .when function when testing get will return the given values
  get<DataType extends BaseClass>(endpoint: string, accessor: BaseDataAccessor,
                                  descriptor: IDataDescriptor<DataType>,
                                  query: Query, subscribe: boolean) {
    if (this.expects.length > 0) {
      const exp = this.expects.shift();
      expect(exp!.endpoint).toEqual(endpoint);
      expect(exp!.query).toEqual(query);
    }

    for (const mock of this.mocks) {
      if (mock.endpoint === endpoint && JSON.stringify(mock.query) === JSON.stringify(query)) {
        return this.createCollection(endpoint, accessor, descriptor, query, mock.returnValue);
      }
    }
    throw new Error(`No return value for: ${endpoint} (${JSON.stringify(query)})`);
  }

  createCollection<DataType extends BaseClass>(restPath: string, accessor: BaseDataAccessor,
                                               descriptor: IDataDescriptor<DataType>, query: Query,
                                               response: any) {
    const collection = new DataCollection<DataType>();
    collection.open(restPath, query, accessor, descriptor, this.webSocketClient);

    // populate the response with ascending id values for convenience
    const fieldId = descriptor.fieldId;
    let idCounter = 1;
    response.forEach((d: any) => {
      if (!d.hasOwnProperty(fieldId)) {
        d[fieldId] = idCounter++;
      }
    });

    collection.initial(response);
    return collection;
  }
}

/*
  This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the
  MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.

  Copyright Buildbot Team Members
*/

import {DataClient} from "./DataClient";
import {Query} from "./DataQuery";
import {BaseClass} from "./classes/BaseClass";
import {BaseDataAccessor} from "./DataAccessor";
import {IDataDescriptor} from "./classes/DataDescriptor";
import {DataCollection} from "./DataCollection";

type MockedResult = {
  endpoint: string;
  query: Query;
  returnValue: any;
}

export class MockDataClient extends DataClient {
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

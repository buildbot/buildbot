/*
  This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the
  MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.

  Copyright Buildbot Team Members
*/

import {type} from "../DataUtils";
import {IDataAccessor} from "../DataAccessor";
import {IDataDescriptor} from "./DataDescriptor";
import {ControlParams, RequestQuery} from "../DataQuery";

export class BaseClass {
  // base endpoint for the items of this class, e.g. "builds", or "builds/12/steps". Full
  // API URL referring to the item is `${endpoint}/${id}`.
  private endpoint: string;
  id: string;
  private accessor: IDataAccessor;

  constructor(accessor: IDataAccessor, endpoint: string, id: string) {
    this.accessor = accessor;
    this.id = id;
    this.endpoint = endpoint;

    // reset endpoint to base
    if (this.id !== null) {
      this.endpoint = type(this.endpoint);
    }
  }

  update(object: any) {
    throw Error("Not implemented");
  }

  toObject() {
    throw Error("Not implemented");
  }

  get<DataType extends BaseClass>(endpoint: string, query: RequestQuery,
                                  descriptor: IDataDescriptor<DataType>) {
    return this.accessor.get(this.endpoint + "/" + this.id + "/" + endpoint,
      query, descriptor);
  }

  control(method: string, params: ControlParams = {}) {
    return this.accessor.control(this.endpoint + "/" + this.id, method, params);;
  }

  protected getPropertiesImpl(endpoint: string, query: RequestQuery) {
    return this.accessor.getProperties(this.endpoint + "/" + this.id + "/" + endpoint, query);
  }
}

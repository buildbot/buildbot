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

import {type} from "../DataUtils";
import {IDataAccessor} from "../DataAccessor";
import IDataDescriptor from "./DataDescriptor";
import {ControlParams, RequestQuery} from "../DataQuery";

export default class BaseClass {
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

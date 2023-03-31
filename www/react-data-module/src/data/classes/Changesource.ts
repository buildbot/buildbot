/*
  This Source Code Form is subject to the terms of
  the Mozilla Public License, v. 2.0. If a copy of the
  MPL was not distributed with this file, You can
  obtain one at https://mozilla.org/MPL/2.0/.

  Copyright Buildbot Team Members
*/

import {BaseClass} from "./BaseClass";
import {IDataDescriptor} from "./DataDescriptor";
import {IDataAccessor} from "../DataAccessor";
import {RequestQuery} from "../DataQuery";

export class Changesource extends BaseClass {
  changesourceid!: number;
  master!: any; // FIXME
  name!: string;

  constructor(accessor: IDataAccessor, endpoint: string, object: any) {
    super(accessor, endpoint, String(object.changesourceid));
    this.update(object);
  }

  update(object: any) {
    this.changesourceid = object.changesourceid;
    this.master = object.master;
    this.name = object.name;
  }

  toObject() {
    return {
      changesourceid: this.changesourceid,
      master: this.master,
      name: this.name,
    };
  }

  static getAll(accessor: IDataAccessor, query: RequestQuery = {}) {
    return accessor.get<Changesource>("changesources", query, changesourceDescriptor);
  }
}

export class ChangesourceDescriptor implements IDataDescriptor<Changesource> {
  restArrayField = "changesources";
  fieldId: string = "changesourceid";

  parse(accessor: IDataAccessor, endpoint: string, object: any) {
    return new Changesource(accessor, endpoint, object);
  }
}

export const changesourceDescriptor = new ChangesourceDescriptor();

/*
  This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the
  MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.

  Copyright Buildbot Team Members
*/

import {IDataAccessor} from "../DataAccessor";

export interface IAnyDataDescriptor {
  restArrayField: string;
}

export interface IDataDescriptor<T> extends IAnyDataDescriptor {
  fieldId: string;
  parse(accessor: IDataAccessor, endpoint: string, object: any): T;
}

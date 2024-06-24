/*
  This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the
  MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.

  Copyright Buildbot Team Members
*/

export type Query = {[key: string]: any};

export type RequestQuery = {
  query?: Query;
  subscribe?: boolean;
  id?: string;
};

export type ControlParams = {[key: string]: any};

type ValueFilter = (v: any) => boolean;

const parseFilter = (fieldAndOperator: string, value: any): ValueFilter | null => {
  if (['field', 'limit', 'offset', 'order', 'property'].indexOf(fieldAndOperator) >= 0) {
    return null;
  }

  if (['on', 'true', 'yes'].indexOf(value) > -1) {
    value = true;
  } else if (['off', 'false', 'no'].indexOf(value) > -1) {
    value = false;
  }

  const [field, operator] = Array.from(fieldAndOperator.split('__'));
  switch (operator) {
    case 'ne': return (v: any) => v[field] !== value;
    case 'lt': return (v: any) => v[field] < value;
    case 'le': return (v: any) => v[field] <= value;
    case 'gt': return (v: any) => v[field] > value;
    case 'ge': return (v: any) => v[field] >= value;
    default: return (v: any) => {
      if (v[field] === value) {
        return true;
      }
      if (Array.isArray(v[field]) && Array.from(v[field]).includes(value)) {
        return true;
      }
      if (Array.isArray(value) && value.length === 0) {
        return true;
      }
      if (Array.isArray(value) && Array.from(value).includes(v[field])) {
        return true;
      }
      return false;
    }
  }
}

export class DataQuery {
  query: Query;
  filters: ValueFilter[] = [];
  order: any | null = null;
  limit: number | null = null;

  constructor(query: Query | null) {
    if (query === null) {
      query = {};
    }
    this.query = query;
    for (let fieldAndOperator in query) {
      const filter = parseFilter(fieldAndOperator, query[fieldAndOperator]);
      if (filter !== null) {
        this.filters.push(filter);
      }
    }
    if ('order' in this.query) {
      this.order = this.query.order;
    }
    if ('limit' in this.query) {
      this.limit = this.query.limit;
    }
  }

  isAllowedByFilters(v: any) {
    for (const filter of this.filters) {
      if (!filter(v)) {
        return false;
      }
    }
    return true;
  }

  filter(array: any[]) {
    let i = 0;
    while (i < array.length) {
      const v = array[i];
      if (this.isAllowedByFilters(v)) {
        i += 1;
      } else {
        array.splice(i, 1);
      }
    }
  }

  applySort(array: any[]) {
    const order = this.order;
    if (order === null) {
      return;
    }
    const compare = (property: string) => {
      let reverse = false;
      if (property[0] === '-') {
        property = property.slice(1);
        reverse = true;
      }

      return (a: any, b: any) => {
        if (reverse) {
          [a, b] = Array.from([b, a]);
        }

        if (a[property] < b[property]) {
          return -1;
        } else if (a[property] > b[property]) {
          return 1;
        } else {
          return 0;
        }
      };
    };
    if (typeof order === 'string') {
      array.sort(compare(order));
    } else if (Array.isArray(order)) {
      array.sort((a: any, b: any) => {
        for (let o of Array.from(order)) {
          const f = compare(o)(a, b);
          if (f) { return f; }
        }
        return 0;
      });
    } else {
      throw Error(`Unsupported order parameter for query {order}`)
    }
  }

  applyLimit(array: any[]) {
    if (this.limit === null) {
      return;
    }
    while (array.length > this.limit) {
      array.pop();
    }
  }
}

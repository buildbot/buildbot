ResultSpecs
-----------

.. py:module:: buildbot.data.resultspec

Result specifications are used by the :ref:`Data_API` to describe the desired results of a :py:meth:`~buildbot.data.connector.DataConnector.get` call.
They can be used to filter, sort and paginate the contents of collections, and to limit the fields returned for each item.

Python calls to :py:meth:`~buildbot.data.connector.DataConnector.get` call can pass a :py:class:`ResultSpec` instance directly.
Requests to the HTTP REST API are converted into instances automatically.

Implementers of Data API endpoints can ignore result specifications entirely, except where efficiency suffers.
Any filters, sort keys, and so on still present after the endpoint returns its result are applied generically.
:py:class:`ResultSpec` instances are mutable, so endpoints that do apply some of the specification can remove parts of the specification.

Result specifications are applied in the following order:

 * Field Selection (fields)
 * Filters
 * Order
 * Pagination (limit/offset)
 * Properties

Only fields & properties are applied to non-collection results.
Endpoints processing a result specification should take care to replicate this behavior.

.. py:class:: ResultSpec

   A result specification has the following attributes, which should be treated as read-only:

   .. py:attribute:: filters

        A list of :py:class:`Filter` instances to be applied.
        The result is a logical AND of all filters.

   .. py:attribute:: fields

        A list of field names that should be included, or ``None`` for no sorting.
        if the field names all begin with ``-``, then those fields will be omitted and all others included.

   .. py:attribute:: order

        A list of field names to sort on.
        if any field name begins with ``-``, then the ordering on that field will be in reverse.

   .. py:attribute:: limit

        The maximum number of collection items to return.

   .. py:attribute:: offset

        The 0-based index of the first collection item to return.

   .. py:attribute:: properties

        A list of :py:class:`Property` instances to be applied.
        The result is a logical AND of all properties.

    All of the attributes can be supplied as constructor keyword arguments.

    Endpoint implementations may call these methods to indicate that they have processed part of the result spec.
    A subsequent call to :py:meth:`apply` will then not waste time re-applying that part.

    .. py:method:: popProperties()

        If a property exists, return its values list and remove it from the result spec.

    .. py:method:: popFilter(field, op)

        If a filter exists for the given field and operator, return its values list and remove it from the result spec.

    .. py:method:: popBooleanFilter(field)

        If a filter exists for the field, remove it and return the expected value (True or False); otherwise return None.
        This method correctly handles odd cases like ``field__ne=false``.

    .. py:method:: popStringFilter(field)

        If one string filter exists for the field, remove it and return the expected value (as string); otherwise return None.

    .. py:method:: popIntegerFilter(field)

        If one integer filter exists for the field, remove it and return the expected value (as integer); otherwise return None.
        raises ValueError if the field is not convertible to integer.

    .. py:method:: removePagination()

        Remove the pagination attributes (:py:attr:`limit` and :py:attr:`offset`) from the result spec.
        And endpoint that calls this method should return a :py:class:`~buildbot.data.base.ListResult` instance with its pagination attributes set appropriately.

    .. py:method:: removeOrder()

        Remove the order attribute.

    .. py:method:: popField(field)

        Remove a single field from the :py:attr:`fields` attribute, returning True if it was present.
        Endpoints can use this in conditionals to avoid fetching particularly expensive fields from the DB API.


    The following method is used internally to apply any remaining parts of a result spec that are not handled by the endpoint.

    .. py:method:: apply(data)

        Apply the result specification to the data, returning a transformed copy of the data.
        If the data is a collection, then the result will be a :py:class:`~buildbot.data.base.ListResult` instance.


.. py:class:: Filter(field, op, values)

    :param string field: the field to filter on
    :param string op: the comparison operator (e.g., "eq" or "gt")
    :param list values: the values on the right side of the operator

    A filter represents a limitation of the items from a collection that should be returned.

    Many operators, such as "gt", only accept one value.
    Others, such as "eq" or "ne", can accept multiple values.
    In either case, the values must be passed as a list.

.. py:class:: Property(values)

    :param list values: the values on the right side of the operator (``eq``)

    A property represents an item of a foreign table.

    In either case, the values must be passed as a list.

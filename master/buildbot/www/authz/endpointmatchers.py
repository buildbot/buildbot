
class EndpointMatcherBase(object):
    def __init__(self, **kwargs):
        pass


class AnyEndpointMatcher(EndpointMatcherBase):
    def __init__(self, **kwargs):
        EndpointMatcherBase.__init__(self, **kwargs)


class ViewBuildsEndpointMatcher(EndpointMatcherBase):
    def __init__(self, **kwargs):
        EndpointMatcherBase.__init__(self, **kwargs)


class StopBuildEndpointMatcher(EndpointMatcherBase):
    def __init__(self, **kwargs):
        EndpointMatcherBase.__init__(self, **kwargs)


class BranchEndpointMatcher(EndpointMatcherBase):
    def __init__(self, **kwargs):
        EndpointMatcherBase.__init__(self, **kwargs)


class ForceBuildEndpointMatcher(EndpointMatcherBase):
    def __init__(self, **kwargs):
        EndpointMatcherBase.__init__(self, **kwargs)

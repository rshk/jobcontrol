class JobControlException(Exception):
    pass


class NotFound(JobControlException):
    """
    Exception used to indicate something was not found
    """
    pass


class MissingDependencies(JobControlException):
    """
    Exception used to indicate a build dependency was missing
    """
    pass

"""
This module contains the exceptions used by JobControl.
"""


class JobControlException(Exception):
    """Base for JobControl exceptions"""
    pass


class NotFound(JobControlException):
    """
    Exception used to indicate something was not found.
    Pretty generic, but useful for returning 404s..
    """
    pass


class MissingDependencies(JobControlException):
    """
    Exception used to indicate a build dependency was not met
    (i.e. job has no successful builds).
    """
    pass


class SkipBuild(JobControlException):
    """
    Exception raised by builds to indicate the current build
    should be skipped, eg. because there is no need for a rebuild.
    """
    pass


class SerializationError(JobControlException):
    """
    Exception raised when serialization of a build's return value
    failed.
    """
    pass

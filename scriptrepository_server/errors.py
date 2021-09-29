"""A set of exception classes to indicate various
error scenarios
"""
import http.client
from .base import ServerResponse


class RequestException(Exception):
    """Generic base exception type
    """

    def __init__(self, summary, detail):
        super(RequestException, self).__init__(summary)
        self.summary = summary
        self.detail = detail
        self.http_error_code = None

    def response(self):
        return ServerResponse(self.http_error_code, message=self.summary,
                              detail=self.detail)


class BadRequestException(RequestException):
    """Indicates a 400 error -  bad request
    """

    def __init__(self, summary, detail):
        super(BadRequestException, self).__init__(summary, detail)
        self.http_error_code = http.client.BAD_REQUEST


class InternalServerError(RequestException):
    """Indicates a 500 error - internal server problem
    """

    def __init__(self):
        super(InternalServerError,
              self).__init__(summary='Server Error. Please contact Mantid support.', detail='')
        self.http_error_code = http.client.INTERNAL_SERVER_ERROR

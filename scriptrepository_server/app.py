"""Defines the WSGI application entry point for the upload server

In order to submit a file, it is necessary to POST a form with the
following fields:
  - author: Name of the author of the file.
  - mail: Email of the author.
  - comment: a description of the file or updates it is being done.
  - file: The file itself.
  - path: The folder where the file must be inserted.

If the values are all valid then the files are committed and uploaded
to the central repository using:
  - git add <file>
  - git commit -m "<comment>" --author "<author> <<email>>"
  - git push

The response body will be a json-encoded dictionary containing:
  - message: A string containing an information message on the outcome of the request. For
             success it is simply 'success'
  - detail: if an error occurred then further details are provided here
  - pub_date: the date and time of the upload in the format  %Y-%b-%d %H:%M:%S

Only POST requests are accepted, any other type will result in a 405 error.

Several query parameters are understood:
 - remove=1: if included the file will be removed rather than uploaded
 - debug=1: if included then the update will happen in the sandbox repository
"""
from __future__ import absolute_import, print_function

import httplib
import os
import time
import traceback
from urlparse import parse_qs

from .base import ScriptRemovalForm, ScriptUploadForm, ServerResponse
from .errors import BadRequestException, InternalServerError, RequestException
from .repository import GitCommitInfo, GitRepository

# Map requests to handlers
# Each handler should have the following structure:
#   def foo_handle(environ)
#      # process the request
#      ...
#      ...
#      return ServerResponse(status_code, ...)
_REQUEST_HANDLERS = {
    'POST': 'handle_post'
}

# Maximum allowed file size
MAX_FILESIZE_BYTES=1*1024*1024

# Comitter's name
COMMITTER_NAME = "mantid-publisher"

# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------
def application(environ, start_response):
    """Called by the webserver when the URL is hit
      :param environ A dictionary of context variables
      :start_response A callback function that will the response to the client
    """
    # Find handler
    handle_attr = _REQUEST_HANDLERS.get(environ['REQUEST_METHOD'],
                                        'null_handler')
    response = globals()[handle_attr](environ)
    # Begin response
    start_response(response.status, response.headers)
    # It is important to return the content within another iterable. The caller
    # iterates over the returned iterable and sends data back with each iteration.
    # The list makes this happen in 1 go
    return [response.content]

# ------------------------------------------------------------------------------
# Handler methods
# ------------------------------------------------------------------------------
def handle_post(environ):
    err_stream = environ["wsgi.errors"]
    try:
        script_form, debug = parse_request(environ)
        local_repo_root = get_local_repo_path(environ, debug, err_stream)
        return update_central_repo(local_repo_root, script_form, err_stream)
    except RequestException, err:
        return err.response()

def null_handler(environ):
    return ServerResponse(httplib.METHOD_NOT_ALLOWED, message=u'Endpoint is ready to accept form uploads.')

# ------------------------------------------------------------------------------
# Request checks
# ------------------------------------------------------------------------------
def parse_request(environ):
    """Check the request return the type to the caller
    """
    query_params = parse_qs(environ["QUERY_STRING"])
    is_upload = ("remove" not in query_params)
    debug = ("debug" in query_params)

    if is_upload:
        cls = ScriptUploadForm
    else:
        cls = ScriptRemovalForm
    script_form, error = cls.create(environ)
    if error:
        raise BadRequestException(summary=error[0], detail='\n'.join(error[1:]))

    return script_form, debug

def get_local_repo_path(environ, debug, err_stream):
    envvar = 'SCRIPT_REPOSITORY_PATH'
    if debug:
        envvar += "_DEBUG"
    try:
        return environ[envvar]
    except KeyError:
        err_stream.write("Script repository upload: Cannot find environment variable pointing to the repository")
        raise InternalServerError()

# ------------------------------------------------------------------------------
# Repository update
# ------------------------------------------------------------------------------
def update_central_repo(local_repo_root, script_form, err_stream):
    """This assumes that the script is running as a user who has permissions
    to push to the central github repository
    """
    git_repo = GitRepository(local_repo_root)
    if hasattr(script_form, 'write_script_to_disk'):
        # size limit
        if script_form.filesize > MAX_FILESIZE_BYTES:
            raise BadRequestException("File is too large.",
                                      "Maximum filesize is {0} bytes".format(MAX_FILESIZE_BYTES))
        filepath, error = script_form.write_script_to_disk(local_repo_root)
        is_upload = True
        if error:
            detail = '\n'.join(error)
            err_stream.write("Script repository upload: error writing script to disk - {0}.".format(detail))
            raise InternalServerError()
    else:
        # Treated as a remove request
        is_upload = False
        filepath = script_form.filepath(local_repo_root)
        if not git_repo.user_can_delete(filepath, script_form.author, script_form.mail):
            raise BadRequestException('Permissions error.',
                                      'You are not allowed to remove this file as it belongs to another user')

    commit_info = GitCommitInfo(author=script_form.author,
                                email=script_form.mail,
                                comment=script_form.comment,
                                filelist=[filepath],
                                committer=COMMITTER_NAME,
                                add=is_upload)
    try:
        published_date = git_repo.commit_and_push(commit_info, add_changes=is_upload)
    except RuntimeError:
        err_stream.write("Script repository upload: git error - {0}.".format(traceback.format_exc()))
        raise InternalServerError()

    return ServerResponse(httplib.OK, message="success",
                          published_date=published_date)

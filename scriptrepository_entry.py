#!/usr/bin/env python
# WSGI entry point for the scriptrepository_server application
# It requires a scriptrepository_server.settings module to be

import os
import sys


settings_file = os.path.join(os.path.dirname(__file__),
                             "scriptrepository_server.settings")
if not os.path.exists(settings_file):
    sys.exit("Cannot find 'scriptrepository_server.settings' file.")
try:
    execfile(settings_file)
except Exception as exc:
    sys.exit("Error processing settings file '{0}'".format(str(exc)))

# Find the application
sys.path.append(SCRIPTREPOSITORY_SERVER_DIR)

# Wrapper application to update the WSGI environ dictionary
def application(environ, start_response):
    from scriptrepository_server.app import (\
        application as _application,
        initialise_logging)
    # Define the location of the cloned repositories
    environ["SCRIPT_REPOSITORY_PATH"] = SCRIPT_REPOSITORY_PATH
    try:
        environ["SCRIPT_REPOSITORY_PATH_DEBUG"] = SCRIPT_REPOSITORY_PATH_DEBUG
    except NameError:
        # Not mandatory to have the debug path
        pass

    # Configure logging
    initialise_logging(default_level=DEFAULT_LOGLEVEL)
    # Hand off to "real" app
    return _application(environ, start_response)

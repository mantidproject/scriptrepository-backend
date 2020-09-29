# upload.mantidproject.org

Here you will find the web application that is responsible for interacting
with Mantid and the scriptrepository to allow uploading of new files.

The application itself uses only packages found in the Python standard library but it requires the `git` command to be accessible and executable. A clone of the repository is required and the web server must ensure that the `SCRIPT_REPOSITORY_PATH` environment points to the cloned copy. The webserver must also have permissions to write to those files and directories.

Requirements:

* A web server providing >= v3.0 of the wsgi interface so that it supports chunked transfer encoding natively

# Running Tests Locally (Linux)

Change to this directory. Create a virtual environment with Python 3 and activate it:

    python3 -m virtualenv -p /usr/bin/python3 ~/.virtualenvs/scriptrepository 
    source ~/.virtualenvs/scriptrepository/bin/activate

Install the required packages:

    python -m pip install -r requirements.txt

Run the tests inside this environment:

    python test/test_server.py

# ScriptRepository Uploader Backend

Here you will find the web application that is responsible for interacting
with Mantid and the scriptrepository to allow uploading of new files.
It essentially acts as middleware to avoid Mantid having to directly
interact with the GitHub API. The application itself uses only packages found in the Python standard library
but it requires the `git` command to be accessible and executable.

The application can be run standalone but in production it is designed to be
executed by a webserver supporting the
[wsgi](https://wsgi.readthedocs.io/en/latest/what.html) interface.

The production instance is deployed to listed at https://upload.mantidproject.org.

## Local Development Setup

For development locally we recommend using a conda environment:

```sh
> conda create -n scriptrepo_server python=3.8
> conda activate scriptrepo_server
> pip install -r requirements.txt
```

Run the tests using `unittest`:

```sh
> python -m unittest
```

## Webserver Configuration Example: nginx

The webserver is required to support chunked-transfer encoding, e.g. wsgi >= 3.0.

See the [ansible-linode](https://github.com/mantidproject/ansible-linode/tree/main/roles/nginx)
nginx setup for an example of running this with nginx.

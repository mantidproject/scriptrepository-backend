"""A set of helpers to aid handling a request to upload a script file
"""


import cgi
import http.client
import json
from logging import getLogger
import os
import re

# Email regex
MAIL_RE = re.compile(r'[^@]+@[^@]+\.[^@]+')


# ------------------------------------------------------------------------------
class ScriptForm(object):

    required_fields = ("author", "mail", "comment")

    @classmethod
    def create(cls, request_fields):
        # sanity check
        data = dict()
        missing, invalid = [], []
        for name in cls.required_fields:
            if name in request_fields:
                value = request_fields[name].value
                if cls.validate_field(name, value):
                    data[name] = value
                else:
                    invalid.append(name)
            else:
                missing.append(name)
        # endfor
        if len(missing) == 0 and len(invalid) == 0:
            # Use the filtiem not the actual content
            # if we have it
            if "file" in data:
                del data["file"]
                data["fileitem"] = request_fields[name]
            return cls(**data), None
        else:
            summary = 'Incomplete form information supplied.'
            detail = []
            if len(missing) > 0:
                detail.append('Missing fields: ' + ','.join(missing))
            if len(invalid) > 0:
                detail.append('Invalid fields: ' + ','.join(invalid))
            return None, (summary, "\n".join(detail))

    @staticmethod
    def validate_field(name, value):
        if name == "mail":
            return (MAIL_RE.match(value) is not None)
        elif name == "path":
            return ('./' in value and '../' not in value)
        else:
            return (value != '')

    def __init__(self, author, mail, comment):
        self.author = author
        self.mail = mail
        self.comment = comment


# ------------------------------------------------------------------------------
class ScriptUploadForm(ScriptForm):
    """Defines the incoming payload from the client and the fields that
       are expected
    """
    required_fields = ScriptForm.required_fields + ("path", "file")

    def __init__(self, author, mail, comment, path, fileitem):
        super(ScriptUploadForm, self).__init__(author, mail, comment)

        self.rel_path = path
        self.fileitem = fileitem

    @property
    def filesize(self):
        return len(self.fileitem.value)

    def is_upload(self):
        return True

    def filepath(self, root):
        # strip leading path from filename to avoid directory traversal attacks
        filename = os.path.basename(self.fileitem.filename)
        return os.path.join(root, self.rel_path, filename)

    def write_script_to_disk(self, root):
        """Dumps the uploaded file contents to disk. The location is
        formed by os.path.join(root, self.rel_path), where rel_path is
        the path specified by the form
        """
        filepath = self.filepath(root)
        if os.path.isdir(filepath):
            return None, ("Cannot replace directory with a file.",
                          "{0} already exists as a directory.".format(filepath))
        try:
            # Make sure the directory exists
            dirpath = os.path.dirname(filepath)
            if not os.path.exists(dirpath):
                os.makedirs(dirpath)
            open(filepath, 'wb').write(self.fileitem.file.read())
        except Exception as err:
            return None, ("Unable to write script to disk.", str(err))

        return filepath, None


class ScriptRemovalForm(ScriptForm):

    extra_fields = ("file_n",)
    required_fields = ScriptForm.required_fields + extra_fields

    def __init__(self, author, mail, comment, file_n):
        super(ScriptRemovalForm, self).__init__(author, mail, comment)
        self.filename = file_n

    def is_upload(self):
        return False

    def filepath(self, root):
        return os.path.join(root, self.filename)


class ScriptFormFactory(object):

    @staticmethod
    def create(environ):
        """Create an appropriate scriptform for the environment
        """
        request_fields = cgi.FieldStorage(fp=environ['wsgi.input'],
                                          environ=environ, keep_blank_values=1)
        # This kind of breaks the encapsulation of ScriptRemovalForm and should
        # probably be a chain of responsibility...
        if ScriptRemovalForm.extra_fields[0] not in request_fields:
            # Most of the time users upload things.
            cls = ScriptUploadForm
        else:
            cls = ScriptRemovalForm
        # end

        return cls.create(request_fields)


class ServerResponse(object):

    def __init__(self, status_code, message, detail=None,
                 published_date=None, shell=None):
        self._create_status(status_code)
        self._create_body(message, detail,
                          published_date, shell)
        self._create_headers()

    def _create_status(self, code):
        self.status = "{0} {1}".format(str(code), http.client.responses[code])

    def _create_headers(self):
        self.headers = [
            ('Content-Type', 'application/json; charset=utf-8'),
            ('Content-Length', str(len(self.content)))
        ]

    def _create_body(self, message, detail, published_date, shell):
        detail = detail if detail is not None else ""
        pub_date = published_date if published_date is not None else ""
        shell = shell if shell is not None else ""
        data = dict(message=message, detail=detail,
                    pub_date=pub_date, shell=shell)
        self.content = json.dumps(data).encode('utf-8')

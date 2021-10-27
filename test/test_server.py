import datetime
import json
import logging
import os
import shutil
import subprocess as subp
import sys
import tempfile
import unittest
from webtest import TestApp

# Our application
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from scriptrepository_server.app import application, initialise_logging

# Local server
TEST_APP = None
# Temporary git repository path
TEMP_DIR = os.path.join(tempfile.gettempdir(), 'ScriptUploadServerTest')
TEMP_GIT_REPO_PATH = os.path.join(TEMP_DIR, "scriptrepository_unittest")
# Temporary git repository path
TEMP_GIT_REMOTE_PATH = os.path.join(TEMP_DIR,
                                    "scriptrepository_unittest_remote")
#
GIT_USERNAME = "unittest"
GIT_EMAIL = "builder@email.com"

SCRIPT_CONTENT = \
"""
def hello(name):
    print "Hello, World"
"""

FIRST_COMMIT = None


# ------------------------------------------------------------------------------
def setUpModule():
    global TEST_APP
    initialise_logging(default_level=logging.DEBUG)
    os.environ["GIT_CONFIG_NOSYSTEM"] = "1"
    os.environ["HOME"] = TEMP_DIR
    os.environ["XCD_CONFIG_HOME"] = TEMP_DIR
    TEST_APP = TestApp(application)


def _setup_test_git_repos():
    global FIRST_COMMIT

    os.makedirs(TEMP_GIT_REMOTE_PATH)
    start_dir = os.getcwd()

    # Init the remote
    os.chdir(TEMP_GIT_REMOTE_PATH)
    subp.check_output("git init", stderr=subp.STDOUT, shell=True)
    # Create a commit so we can use reset
    readme = os.path.join(TEMP_GIT_REMOTE_PATH, "README.md")
    with open(readme, 'w') as readme_file:
        readme_file.write("foo")
    subp.check_output(
        f"git add .; git -c user.name='{GIT_USERNAME}' -c user.email={GIT_EMAIL} commit -m'Initial commit'",
        stderr=subp.STDOUT,
        shell=True)
    # Chcekout out to some commit directly so that pushing to master is allowed
    sha1 = subp.check_output("git rev-parse HEAD",
                             stderr=subp.STDOUT,
                             shell=True)
    FIRST_COMMIT = str(sha1.rstrip(), encoding='utf-8')
    subp.check_output(f"git checkout {FIRST_COMMIT}",
                      stderr=subp.STDOUT,
                      shell=True)
    # Clone this so that the clone will have a remote
    os.chdir(os.path.dirname(TEMP_GIT_REPO_PATH))
    cmd = f"git clone {TEMP_GIT_REMOTE_PATH} {TEMP_GIT_REPO_PATH}"
    subp.check_output(cmd, stderr=subp.STDOUT, shell=True)

    # Go back to where we started
    os.chdir(start_dir)


def _remove_directory_no_except(directory, quiet=False):
    try:
        shutil.rmtree(directory)
    except OSError as exc:
        if not quiet:
            print(f"Failed to remove temporary git repo base : {exc}")


class ScriptUploadServerTest(unittest.TestCase):
    def setUp(self):
        try:
            _remove_directory_no_except(TEMP_DIR, quiet=True)
            _setup_test_git_repos()
        except Exception as exc:
            print(f"Failed to setup temporary git repo : {exc}")
            _remove_directory_no_except(TEMP_DIR)
            self.fail()

    def tearDown(self):
        _remove_directory_no_except(TEMP_DIR)

    # ---------------- Success cases ---------------------

    def test_app_returns_200_for_successful_upload_in_root_folder(self):
        extra_environ = {"SCRIPT_REPOSITORY_PATH": TEMP_GIT_REPO_PATH}
        data = dict(author='Joe Bloggs',
                    mail='first.last@domain.com',
                    comment='Added new file',
                    path='./')
        response = TEST_APP.post('/',
                                 extra_environ=extra_environ,
                                 params=data,
                                 upload_files=[("file", "userscript.py",
                                                SCRIPT_CONTENT.encode('utf-8'))
                                               ],
                                 status='*')
        self.check_replied_content(expected_json=dict(
            message='success',
            detail='',
            pub_date=self._now_as_str(),
            shell=''),
                                   actual_str=response.body)
        expected_resp = {
            'status': '200 OK',
            'content-length': 85,
            'content-type': 'application/json'
        }
        self.check_response(expected=expected_resp, actual=response)

        # Is the file where we expect it to be
        repo_file = os.path.join(TEMP_GIT_REPO_PATH, "userscript.py")
        self.assertTrue(os.path.exists(repo_file))
        with open(repo_file, 'r') as userscript:
            content = userscript.read()
        self.assertEqual(SCRIPT_CONTENT, content)

    def test_app_returns_200_for_successful_upload_in_subfolder(self):
        extra_environ = {"SCRIPT_REPOSITORY_PATH": TEMP_GIT_REPO_PATH}
        data = dict(author='Joe Bloggs',
                    mail='first.last@domain.com',
                    comment='Added new file',
                    path='./muon')
        response = TEST_APP.post('/',
                                 extra_environ=extra_environ,
                                 params=data,
                                 upload_files=[("file", "userscript.py",
                                                SCRIPT_CONTENT.encode('utf-8'))
                                               ],
                                 status='*')
        self.check_replied_content(expected_json=dict(
            message='success',
            detail='',
            pub_date=self._now_as_str(),
            shell=''),
                                   actual_str=response.body)
        expected_resp = {
            'status': '200 OK',
            'content-length': 85,
            'content-type': 'application/json'
        }
        self.check_response(expected=expected_resp, actual=response)

        # Is the file where we expect it to be
        repo_file = os.path.join(TEMP_GIT_REPO_PATH, "muon", "userscript.py")
        self.assertTrue(os.path.exists(repo_file))
        with open(repo_file, 'r') as userscript:
            content = userscript.read()

        self.assertEqual(SCRIPT_CONTENT, content)

    def test_app_returns_200_for_successful_remove_request(self):
        # Commit test file
        repo_file = os.path.join(TEMP_GIT_REPO_PATH, "muon", "userscript.py")
        start_dir = os.getcwd()
        try:
            os.chdir(TEMP_GIT_REPO_PATH)
            os.mkdir(os.path.dirname(repo_file))
            with open(repo_file, 'w') as userscript:
                userscript.write("foo")
            author = 'Joe Bloggs'
            mail = 'first.last@domain.com'
            subp.check_output(
                f'git add .; git -c user.name="{author}" -c user.email="{mail}" commit -m"Added new file"; git push origin master',
                stderr=subp.STDOUT,
                shell=True)
        finally:
            os.chdir(start_dir)

        # Test remove
        extra_environ = {"SCRIPT_REPOSITORY_PATH": TEMP_GIT_REPO_PATH}
        data = dict(author=author,
                    mail=mail,
                    comment='Removed file',
                    file_n='muon/userscript.py')
        response = TEST_APP.post('/',
                                 extra_environ=extra_environ,
                                 params=data,
                                 status='*')

        self.check_replied_content(expected_json=dict(message='success',
                                                      detail='',
                                                      pub_date='',
                                                      shell=''),
                                   actual_str=response.body)
        # Is the file removed
        self.assertTrue(not os.path.exists(repo_file))
        expected_resp = {
            'status': '200 OK',
            'content-length': 65,
            'content-type': 'application/json'
        }
        self.check_response(expected=expected_resp, actual=response)

    def test_app_returns_200_for_successful_overwrite_of_existing_file(self):
        # Commit test file
        repo_file = os.path.join(TEMP_GIT_REPO_PATH, "muon", "userscript.py")
        os.mkdir(os.path.dirname(repo_file))
        with open(repo_file, 'w') as userscript:
            userscript.write("foo")

        start_dir = os.getcwd()
        os.chdir(TEMP_GIT_REPO_PATH)
        author = 'Joe Bloggs'
        mail = 'first.last@domain.com'
        subp.check_output(
            'git add .; git commit -m"Added new file" --author="{0} <{1}>"; git push origin master; exit 0'
            .format(author, mail),
            stderr=subp.STDOUT,
            shell=True)
        os.chdir(start_dir)

        extra_environ = {"SCRIPT_REPOSITORY_PATH": TEMP_GIT_REPO_PATH}
        data = dict(author=author,
                    mail=mail,
                    comment='Updated file',
                    path='./muon')
        response = TEST_APP.post('/',
                                 extra_environ=extra_environ,
                                 params=data,
                                 upload_files=[("file", "userscript.py",
                                                SCRIPT_CONTENT.encode('utf-8'))
                                               ],
                                 status='*')
        self.check_replied_content(expected_json=dict(
            message='success',
            detail='',
            pub_date=self._now_as_str(),
            shell=''),
                                   actual_str=response.body)
        expected_resp = {
            'status': '200 OK',
            'content-length': 85,
            'content-type': 'application/json'
        }
        self.check_response(expected=expected_resp, actual=response)

        # Is the file where we expect it to be. We need to flip the remote back to master to check this
        os.chdir(TEMP_GIT_REMOTE_PATH)
        subp.check_output('git checkout master',
                          stderr=subp.STDOUT,
                          shell=True)
        os.chdir(start_dir)

        repo_file = os.path.join(TEMP_GIT_REPO_PATH, "muon", "userscript.py")
        remote_file = os.path.join(TEMP_GIT_REMOTE_PATH, "muon",
                                   "userscript.py")
        self.assertTrue(os.path.exists(repo_file))
        self.assertTrue(os.path.exists(remote_file))
        with open(repo_file, 'r') as repo_file_handle:
            repo_content = repo_file_handle.read()
        self.assertEqual(SCRIPT_CONTENT, repo_content)
        with open(remote_file, 'r') as remote_file_handle:
            remote_content = remote_file_handle.read()
        self.assertEqual(SCRIPT_CONTENT, remote_content)

    # ---------------- Failure cases ---------------------

    def test_app_returns_405_for_non_POST_requests(self):
        response = TEST_APP.get('/', expect_errors=True)
        self.check_replied_content(expected_json=dict(
            message='Endpoint is ready to accept form uploads.',
            detail='',
            pub_date='',
            shell=''),
                                   actual_str=response.body)
        expected_resp = {
            'status': '405 Method Not Allowed',
            'content-length': 99,
            'content-type': 'application/json'
        }
        self.check_response(expected=expected_resp, actual=response)

    def test_POST_of_form_without_all_information_produces_400_error(self):
        data = dict(author='Joe Bloggs',
                    mail='first.last@domain.com',
                    comment='Test comment',
                    path='./muon')
        response = TEST_APP.post('/', data, expect_errors=True)
        self.check_replied_content(expected_json=dict(
            message='Incomplete form information supplied.',
            detail='Missing fields: file',
            pub_date='',
            shell=''),
                                   actual_str=response.body)
        expected_resp = {
            'status': '400 Bad Request',
            'content-length': 115,
            'content-type': 'application/json'
        }
        self.check_response(expected=expected_resp, actual=response)

    def test_POST_of_form_with_invalid_fields_produces_400_error(self):
        data = dict(author='', mail='joe.bloggs', comment='', path='')
        response = TEST_APP.post('/', data, expect_errors=True)
        expected_content = dict(
            message='Incomplete form information supplied.',
            detail=
            'Missing fields: file\nInvalid fields: author,mail,comment,path',
            pub_date='',
            shell='')
        self.check_replied_content(expected_json=expected_content,
                                   actual_str=response.body)
        expected_resp = {
            'status': '400 Bad Request',
            'content-length': 157,
            'content-type': 'application/json'
        }
        self.check_response(expected=expected_resp, actual=response)

    def test_script_over_max_size_returns_400_error(self):
        extra_environ = {"SCRIPT_REPOSITORY_PATH": TEMP_GIT_REPO_PATH}
        data = dict(author='Joe Bloggs',
                    mail='first.last@domain.com',
                    comment='Test comment',
                    path='./muon')
        # Write a "big" file
        big_script = tempfile.NamedTemporaryFile(delete=False)
        limit = 1024 * 1024
        for i in range(limit + 1):
            big_script.write(b"1")
        big_script.close()

        response = TEST_APP.post('/',
                                 extra_environ=extra_environ,
                                 expect_errors=True,
                                 params=data,
                                 upload_files=[("file", big_script.name)])
        os.remove(big_script.name)
        self.check_replied_content(expected_json=dict(
            message='File is too large.',
            detail='Maximum filesize is 1048576 bytes',
            pub_date='',
            shell=''),
                                   actual_str=response.body)
        expected_resp = {
            'status': '400 Bad Request',
            'content-length': 109,
            'content-type': 'application/json'
        }
        self.check_response(expected=expected_resp, actual=response)

    def test_app_returns_400_trying_to_remove_file_by_different_author(self):
        # Commit test file
        repo_file = os.path.join(TEMP_GIT_REPO_PATH, "muon", "userscript.py")
        os.mkdir(os.path.dirname(repo_file))
        with open(repo_file, 'w') as userscript:
            userscript.write("foo")

        start_dir = os.getcwd()
        os.chdir(TEMP_GIT_REPO_PATH)
        author = "Jenny Bloggs"
        mail = "j.b@testdomain.com"
        stdout = subp.check_output(
            f'git add . && git -c user.name="{author}" -c user.email="{mail}" commit -m"Added new file" && git push origin master; exit 0'
            .format(author, mail),
            stderr=subp.STDOUT,
            shell=True)
        os.chdir(start_dir)

        # Test remove
        extra_environ = {"SCRIPT_REPOSITORY_PATH": TEMP_GIT_REPO_PATH}
        data = dict(author='Joe Bloggs',
                    mail='first.last@domain.com',
                    comment='Removed file',
                    file_n='muon/userscript.py')
        response = TEST_APP.post('/',
                                 extra_environ=extra_environ,
                                 params=data,
                                 status='*')
        self.check_replied_content(expected_json=dict(
            message='Permissions error.',
            detail=
            'You are not allowed to remove this file as it belongs to another user',
            pub_date='',
            shell=''),
                                   actual_str=response.body)
        expected_resp = {
            'status': '400 Bad Request',
            'content-length': 145,
            'content-type': 'application/json'
        }
        self.check_response(expected=expected_resp, actual=response)

        # Is the file still there?
        self.assertTrue(os.path.exists(repo_file))

    def test_server_without_correct_environment_returns_500_error(self):
        data = dict(author='Joe Bloggs',
                    mail='first.last@domain.com',
                    comment='Test comment',
                    path='./muon')
        response = TEST_APP.post('/',
                                 data,
                                 upload_files=[("file", "userscript.py",
                                                SCRIPT_CONTENT.encode('utf-8'))
                                               ],
                                 expect_errors=True)
        self.check_replied_content(expected_json=dict(
            message='Server Error. Please contact Mantid support.',
            detail='',
            pub_date='',
            shell=''),
                                   actual_str=response.body)
        expected_resp = {
            'status': '500 Internal Server Error',
            'content-length': 102,
            'content-type': 'application/json'
        }
        self.check_response(expected=expected_resp, actual=response)

    # -------------------------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------------------------

    def check_response(self, expected, actual):
        self.assertEqual(expected['status'], actual.status)
        self.assertEqual(expected['content-type'], actual.content_type)
        self.assertEqual(expected['content-length'], actual.content_length)

    def check_replied_content(self, expected_json, actual_str):
        actual_json = json.loads(actual_str)
        # Check the published date manually
        actual_pub_date = actual_json["pub_date"]
        del actual_json["pub_date"]
        expected_pub_date = expected_json["pub_date"]
        del expected_json["pub_date"]

        self.assertEqual(expected_json, actual_json)
        # The pub_date is simply checked that the date portion agrees
        if (expected_pub_date != actual_pub_date) and (expected_pub_date !=
                                                       ''):
            # create full datetime objects from both
            expected_date = datetime.datetime.strptime(expected_pub_date,
                                                       "%Y-%b-%d %H:%M:%S")
            try:
                actual_date = datetime.datetime.strptime(
                    actual_pub_date, "%Y-%b-%d %H:%M:%S")
            except ValueError:
                self.fail(
                    "response pub_date '{0}' cannot be parsed as a datetime object"
                    .format(actual_pub_date))
            # Just check the dates
            self.assertEqual(self._date_as_str(expected_date.date()),
                             self._date_as_str(actual_date))

    def _now_as_str(self):
        return datetime.date.today().strftime("%Y-%b-%d %H:%M:%S")

    def _date_as_str(self, date):
        return date.strftime("%Y-%b-%d")


# ------------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()

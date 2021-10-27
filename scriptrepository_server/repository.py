"""Classes to model a Git repository. Methods just call
out to the shell git command.

The support is limited to the following abilities:
 - pull/push
 - commit
"""
from contextlib import contextmanager
import os
import subprocess as subp
import time


# ------------------------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------------------------
def _git(cmd, args, username=None, email=None):
    args.insert(0, cmd)
    if username is not None and email is not None:
        config = ['-c', 'user.name="{0}"'.format(username),
                  '-c', 'user.email="{0}"'.format(email)]
        config.extend(args)
        args = config

    return _shellcmd("git", args)


def _shellcmd(cmd, args=[]):
    """Use subprocess to call a given command.
    Return stdout/stderr as a str object if an error occurred
    """
    cmd = [cmd]
    cmd.extend(args)
    try:
        p = subp.Popen(cmd, stdout=subp.PIPE, stderr=subp.PIPE)
    except ValueError as err:
        raise RuntimeError(err)
    stdout, stderr = p.communicate()
    if p.returncode == 0:
        return str(stdout, encoding='utf-8')
    else:
        raise RuntimeError(stdout + stderr)


@contextmanager
def transaction(git_repo):
    dir_on_enter = os.getcwd()
    os.chdir(git_repo.root)
    git_repo.begin()
    try:
        yield None
    except Exception as exc:
        git_repo.rollback()
        os.chdir(dir_on_enter)
        raise exc
    else:
        os.chdir(dir_on_enter)


@contextmanager
def dir_change(newdir):
    dir_on_enter = os.getcwd()
    os.chdir(newdir)
    yield None
    os.chdir(dir_on_enter)


# ------------------------------------------------------------------------------
# Classes
# ------------------------------------------------------------------------------
class GitRepository(object):
    """Models a git repo. Currently it needs to have been cloned first.
    """

    def __init__(self, path, remote='origin', branch='master'):
        if not os.path.exists(path):
            raise ValueError('Unable to find git repository at "{0}". '
                             'It must be have been cloned first.'.format(path))
        self.root = path
        self.remote = remote
        self.branch = branch

    def begin(self):
        """Capture the current state so that we can rollback"""
        self._sha1_at_begin = _git("rev-parse", ["HEAD"]).rstrip()

    def rollback(self):
        self.reset(self._sha1_at_begin)

    def commit_and_push(self, commit, add_changes=True):
        """This method is transactional. Any failure results in everything
        being rolled back
        """
        with transaction(self):
            if add_changes:
                pub_date = self._published_date(commit.filelist[0])
                self.add(commit.filelist)
            else:
                self.remove(commit.filelist)
                pub_date = ''
            self.commit(commit.author, commit.email,
                        commit.committer, commit.comment)
            self.push(self.remote, self.branch)

        return pub_date

    def reset(self, sha1):
        """Performs a hard reset to the given treeish reference"""
        return _git("reset", args=["--hard", sha1])

    def add(self, filelist):
        _git("add", filelist)

    def remove(self, filelist):
        _git("rm", filelist)

    def user_can_delete(self, filename, author, mail):
        with dir_change(self.root):
            file_owner = _git("log", ['-1', '--format=%an <%ae>', '--', filename]).rstrip()
            req_user = '{0} <{1}>'.format(author, mail)
        return (req_user == file_owner)

    def commit(self, author, email, committer, msg):
        """Commits all of the changes detailed by the CommitInfo object"""
        # We don't need to worry about spaces as each argument
        # is fed through separately to subprocess.Popen
        msg = '-m {0}'.format(msg)

        _git('commit', [msg], username=author, email=email)

    def sync_with_remote(self):
        """After this method call the local repository will match the remote"""
        with dir_change(self.root):
            self.reset(self.remote + "/" + self.branch)
            # Update
            self.pull(rebase=True)

    def pull(self, rebase=True):
        args = ["--rebase"] if rebase else []
        _git("pull", args)

    def push(self, remote, branch):
        _git("push", [remote, branch])

    def _published_date(self, filepath):
        timeformat = "%Y-%b-%d %H:%M:%S"
        stat = os.stat(filepath)
        modified_time = int(stat.st_mtime)
        # The original code added 2 minutes to the modification date of the file
        # so we preserve this behaviour here
        return time.strftime(timeformat, time.gmtime(modified_time + 120))


class GitCommitInfo(object):
    """Models a git commit"""

    def __init__(self, author, email, comment, filelist,
                 committer=None, add=True):
        self.author = author
        self.committer = committer if committer is not None else author
        self.email = email
        self.comment = comment
        self.filelist = filelist
        self.add = add

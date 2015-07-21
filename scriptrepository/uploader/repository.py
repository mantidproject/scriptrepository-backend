"""Classes to model a Git repository. Methods just call
out to the shell git command.

The support is limited to the following abilities:
 - pull/push
 - commit
"""
from contextlib import contextmanager
import os
import subprocess as subp

# ------------------------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------------------------

def _shellcmd(cmd, args):
    """Use subprocess to call a given command.
    Return stdout/stderr if an error occurred
    """
    cmd = '{0} {1}'.format(cmd, ' '.join(args))
    error = None
    try:
        subp.check_output(cmd, stderr=subp.STDOUT,
                          shell=True)
    except subp.CalledProcessError, err:
        error = str(err)
    return error

@contextmanager
def _directory(path):
    dir_on_enter = os.getcwd()
    os.chdir(path)
    yield
    os.chdir(dir_on_enter)

# ------------------------------------------------------------------------------
# Classes
# ------------------------------------------------------------------------------
class GitRepository(object):
    """Models a git repo. Currently it needs to have been cloned first.
    """

    def __init__(self, path):
        if not os.path.exists(path):
            raise ValueError('Unable to find git repository at "{0}". '\
                             'It must be have been cloned first.'.format(path))
        self.root = path

    def commit_and_push(self, commit, reset_first=True):
        with _directory(self.root):
            error = None
            if reset_first:
                error = self.reset("origin/master")
            if error:
                return ["Git error", error]

    def commit(self, commit):
        """Commits all of the changes detailed by the CommitInfo object"""
        author = '--author="{0} <{1}>"'.format(commit.author, commit.email)
        msg = '--message="{0}"'.format(commit.comment)

        os.environ['GIT_COMMITTER_NAME'] = commit.committer
        error = self._git('commit',[msg, author])
        del os.environ["GIT_COMMITTER_NAME"]

        return error

    def pull(self, rebase=True):
        pass

    def push(self):
        pass

    def reset(self, sha1):
        """Performs a hard reset to the given treeish reference"""
        return self._git("reset", args=["--hard",sha1])

    def _git(self, cmd, args):
        args.insert(0, cmd)
        return _shellcmd("git", args)

class GitCommitInfo(object):
    """Models a git commit"""

    def __init__(self, author, email, comment, filelist, committer=None):
        self.author = author
        self.committer = committer if committer is not None else author
        self.email = email
        self.comment = comment
        self.filelist = filelist

#!/usr/bin/env python3

import os
import sys
import getpass
import argparse
from pathlib import Path
from glob import glob
from collections import defaultdict

from fuzzywuzzy import process
from pygit2 import Repository
from pygit2 import Signature
from pygit2 import Remote
from pygit2 import KeypairFromAgent
from pygit2 import RemoteCallbacks
from pygit2 import GIT_STATUS_CURRENT
from pygit2 import GIT_STATUS_WT_NEW
from pygit2 import GIT_STATUS_WT_MODIFIED
from pygit2 import GIT_STATUS_WT_DELETED
from pygit2 import GIT_STATUS_WT_TYPECHANGE
from pygit2 import GIT_STATUS_INDEX_TYPECHANGE
from pygit2 import GIT_STATUS_WT_RENAMED
from pygit2 import GIT_STATUS_WT_UNREADABLE
from pygit2 import GIT_STATUS_IGNORED
from pygit2 import GIT_STATUS_CONFLICTED
from pygit2 import GitError

# Status flags for a single file.
# A combination of these values will be returned to indicate the status of
# a file.  Status compares the working directory, the index, and the
# current HEAD of the repository.  The `GIT_STATUS_INDEX` set of flags
# represents the status of file in the index relative to the HEAD, and the
# `GIT_STATUS_WT` set of flags represent the status of the file in the
# working directory relative to the index.
#
# working tree (WT) -> index -> HEAD
#
# becaue I am working to update the index to match the working directory/tree
# will only need to work with the GIT_STATUS_WT. Sadly git_index_update_all
# from libgit2 does not have a method in pygit2 so I need to do this myself.
#
# GIT_STATUS_CURRENT
# GIT_STATUS_WT_NEW                  index.add()
# GIT_STATUS_WT_MODIFIED             index.add()
# GIT_STATUS_WT_DELETED              index.remove()
# GIT_STATUS_WT_TYPECHANGE           symlink to file or file to symlink resolve manually
# GIT_STATUS_INDEX_TYPECHANGE        symlink to file or file to symlink resolve manually
# GIT_STATUS_WT_RENAMED              index.add()
# GIT_STATUS_WT_UNREADABLE           error
# GIT_STATUS_IGNORED                 well just ignore it I guess
# GIT_STATUS_CONFLICTED              error

class GitStatusBot():

    def __init__(self, paths):
        self.paths = paths
        self.glob_pattern = '/**/.git'
        self.committer = Signature('GitStatusBot', 'gitstat@fallalex.com')
        self.push_user = 'git'
        self.flagerrors = [GIT_STATUS_CONFLICTED, GIT_STATUS_WT_UNREADABLE,\
                           GIT_STATUS_WT_TYPECHANGE, GIT_STATUS_INDEX_TYPECHANGE]
        self.flagflags  = [GIT_STATUS_WT_NEW, GIT_STATUS_WT_RENAMED,\
                           GIT_STATUS_WT_MODIFIED, GIT_STATUS_WT_DELETED]
        self.find_repos()
        self.grab_latest()


    def grab_latest(self):
        self.ahead_repos()
        self.dirty_repos()


    def match_list(self, query, items=None):
        if items is None:
            items = list(self.repos.keys())
        query = str(query)
        if query.isdigit():
            if int(query) in range(1,len(items)+1):
                return sorted(items)[int(query)-1]
        return False


    def prompt_int_range(self, question, range_list, cancel=True, every=True):
        cancel_str = ''
        if cancel:
            cancel_valid = {'c', 'cancel', 'q', 'quit'}
            cancel_str = '/cancel'
        every_str = ''
        if every:
            every_valid = {'a', 'all'}
            every_str = '/all'
        prompt =(
                ' ['
                + str(min(range_list))
                + '-'
                + str(max(range_list))
                + every_str
                + cancel_str
                + '] ')
        while True:
            selection = input(question + prompt)
            if selection.isdigit() and int(selection) in range_list:
                return int(selection)
            if every is True and selection.lower() in every_valid:
                return 'all'
            if cancel is True and selection.lower() in cancel_valid:
                return False


    def match(self, query):
        query = str(query)
        # match all
        if query == 'all':
            return  sorted(list(self.repos.keys()))

        # allow current directory 'dot' syntax
        if query.strip() == '.':
            query = str(Path(os.getcwd()).parts[-1])

        # exact match
        if query in self.repos:
            return [query]

        # match number from list display
        match = self.match_list(query)
        if match:
            return [match]

        # fuzzy match
        matches = process.extract(query, list(self.repos.keys()))

        # no match if below threshold
        max_ratio = max([x[1] for x in matches])
        if max_ratio < 65:
            return False

        # list of top matches
        # ask which match to use
        matches = [m[0] for m in matches if m[1] == max_ratio]
        if len(matches) > 1:
            print(self.list_repos(matches))
            result = self.prompt_int_range('Multiple matches, which one(s)?',
                    list(range(1,len(matches)+1)))
            if result is False:
                return False
            elif result is True:
                return sorted(matches)
            else:
                return [self.match_list(result, matches)]
        else:
            return matches


    def git_flags(self, repo):
        flag = ''
        if repo in self.dirty:
            flag += '*'
        else:
            flag += ' '
        if repo in self.ahead:
            flag += '^'
        else:
            flag += ' '
        return flag


    def list_repos(self, repo_list=None):
        if repo_list is None:
            repo_list = list(self.repos.keys())
        if len(repo_list) == 0:
            return False
        digits = len(str(len(repo_list)))
        id_dent = ' ' * digits
        list_str = ''
        for idx, repo in enumerate(sorted(repo_list)):
            flags = ''
            id_col = id_dent[:digits - len(str(idx + 1))] + str(idx + 1) + ')'
            list_str += id_col + self.git_flags(repo) + ' ' + repo + '\n'
        return list_str


    def find_repos(self):
        self.repos = defaultdict(lambda: defaultdict(None))
        for path in self.paths:
            if path.is_dir():
                glob_str = str(path) + self.glob_pattern
                for path in glob(glob_str, recursive=True):
                    path = Path(path)
                    repo = str(path.parts[-2])
                    self.repos[repo]['path'] = path
                    self.repos[repo]['obj'] = Repository(str(path))


    def dirty_repos(self):
        self.dirty = set()
        for repo, v in self.repos.items():
            status = v['obj'].status()
            dirt = list()
            for filepath, flag in status.items():
                if flag in self.flagflags:
                    dirt.append((filepath, flag))
                if flag in self.flagerrors:
                    exit("Error", self.flagerrors, flag, filepath, "resolve manually")
            if len(dirt):
                self.dirty.add(repo)
                self.repos[repo]['dirt'] = tuple(sorted(dirt))


    def ahead_repos(self):
        self.ahead = set()
        branches = {'master', 'origin/master'}
        for repo, v in self.repos.items():
            if set(v['obj'].branches) == branches:
                repo_branches = v['obj'].branches
                local = repo_branches['master']
                origin = repo_branches['origin/master']
                if local.is_head() and local.target != origin.target:
                    self.ahead.add(repo)


    def git_update(self, repo):
        if repo in self.dirty:
            repo_obj = self.repos[repo]['obj']
            index = repo_obj.index
            index.read()
            if 'dirt' in self.repos[repo]:
                for path, flag in self.repos[repo]['dirt']:
                    if flag == GIT_STATUS_WT_DELETED:
                        index.remove(path)
                    else:
                        index.add(path)
                index.write()
                return True
        return False


    def git_commit(self, repo, msg):
        repo_obj = self.repos[repo]['obj']
        index = repo_obj.index
        index.read()
        try:
            repo_obj.create_commit(
                repo_obj.head.name,
                repo_obj.default_signature,
                self.committer,
                msg,
                index.write_tree(),
                [repo_obj.head.get_object().hex])
            return True
        except Exception as e:
            return e


    def git_push(self, repo):
        if repo in self.ahead:
            repo_obj = self.repos[repo]['obj']
            origin = repo_obj.remotes['origin']
            credentials = KeypairFromAgent(self.push_user)
            origin.credentials = credentials
            callbacks = RemoteCallbacks(credentials=credentials)
            try:
                origin.push(
                    [repo_obj.head.name],
                    callbacks=callbacks)
                return True
            except GitError as e:
                return e
        return False


def cli_parse():
    parser = argparse.ArgumentParser(description='Git Status Bot')
    parser.add_argument('repo',
                        nargs='?',
                        type=str,
                        help='run against this repo, uses fuzzy search',
                        metavar='R')
    parser.add_argument('-l',
                        '--list',
                        action='store_true',
                        help='list repos directroy names')
    parser.add_argument('-s',
                        '--sync',
                        action='store_true',
                        help="equivalent to '-ucp'")
    parser.add_argument('-u',
                        '--update',
                        action='store_true',
                        help='git update (add and rm)')
    parser.add_argument('-c',
                        '--commit',
                        action='store_true',
                        help='git commit')
    parser.add_argument('-m',
                        '--message',
                        type=str,
                        help='commit message',
                        metavar='M')
    parser.add_argument('-p',
                        '--push',
                        action='store_true',
                        help='git push origin/master')
    parser.add_argument('-f',
                        '--force',
                        action='store_true',
                        help='do not prompt')
    parser.add_argument('-q',
                        '--quiet',
                        action='store_true',
                        help='no output')
    args = parser.parse_args()
    if args.sync:
        args.update = True
        args.commit = True
        args.push = True
    return args

def main():
    args = cli_parse()
    home = Path.home()
    paths = ['scripts', 'configuration', 'development', '.password-store', 'ansible','vimwiki']
    paths = [home / Path(path) for path in paths]
    if args.message is None:
        args.message = 'committed by gitstat.py'

    gitbot = GitStatusBot(paths)

    if args.list:
        print(gitbot.list_repos())
        sys.exit()

    if args.repo is None:
        print(gitbot.list_repos())
        entry = gitbot.prompt_int_range(
            "Which repo(s)?",
            list(range(1,len(gitbot.repos)+1)))

        if entry == False:
            sys.exit()
        else:
            repos = gitbot.match(entry)

    if args.repo:
        repos = gitbot.match(args.repo)

    if not isinstance(repos, list):
        sys.exit()

    if args.update:
        for repo in repos:
            if gitbot.git_update(repo):
                print('Indexed', repo)
        gitbot.grab_latest()

    if args.commit:
        for repo in repos:
            result = gitbot.git_commit(repo, args.message)
            if result is True:
                print('Committed', repo)
            else:
                print(repo, result)
        gitbot.grab_latest()

    if args.push:
        for repo in repos:
            result = gitbot.git_push(repo)
            if result is True:
                print('Pushed', repo)
            else:
                print(repo, result)

    sys.exit()


if __name__ == "__main__": main()


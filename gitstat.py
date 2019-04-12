#!/usr/bin/env python3

import os
import sys
import argparse
from pathlib import Path
from glob import glob
from collections import defaultdict
from fuzzywuzzy import process
import pygit2
from pygit2 import Repository
from pygit2 import Signature
from pygit2 import Remote
from pygit2 import KeypairFromAgent
from pygit2 import RemoteCallbacks
from pygit2 import GitError

# Status flags for a single file.
# A combination of these values will be returned to indicate the status of
# a file.  Status compares the working directory, the index, and the
# current HEAD of the repository.  The `GIT_STATUS_INDEX` set of flags
# represents the status of file in the index relative to the HEAD, and the
# `GIT_STATUS_WT` set of flags represent the status of the file in the
# working directory relative to the index.

class GitStatusBot():

    def __init__(self, paths):
        self.paths = paths
        self.glob_pattern = '/**/.git'
        self.committer = Signature('GitStatusBot', 'gitstat@fallalex.com')
        self.push_user = 'git'
        self.flagerrors = ['GIT_STATUS_CONFLICTED', 'GIT_STATUS_WT_UNREADABLE',\
                           'GIT_STATUS_WT_TYPECHANGE', 'GIT_STATUS_INDEX_TYPECHANGE']
        self.flagupdate = ['GIT_STATUS_WT_NEW', 'GIT_STATUS_WT_RENAMED',\
                           'GIT_STATUS_WT_MODIFIED', 'GIT_STATUS_WT_DELETED']
        self.flagcommit = ['GIT_STATUS_INDEX_NEW', 'GIT_STATUS_INDEX_RENAMED',\
                           'GIT_STATUS_INDEX_MODIFIED', 'GIT_STATUS_INDEX_DELETED']
        self.status_flags = {'GIT_STATUS_CURRENT'          : pygit2.GIT_STATUS_CURRENT,\
                             'GIT_STATUS_INDEX_NEW'        : pygit2.GIT_STATUS_INDEX_NEW,\
                             'GIT_STATUS_INDEX_MODIFIED'   : pygit2.GIT_STATUS_INDEX_MODIFIED,\
                             'GIT_STATUS_INDEX_DELETED'    : pygit2.GIT_STATUS_INDEX_DELETED,\
                             'GIT_STATUS_INDEX_RENAMED'    : pygit2.GIT_STATUS_INDEX_RENAMED,\
                             'GIT_STATUS_INDEX_TYPECHANGE' : pygit2.GIT_STATUS_INDEX_TYPECHANGE,\
                             'GIT_STATUS_WT_NEW'           : pygit2.GIT_STATUS_WT_NEW,\
                             'GIT_STATUS_WT_MODIFIED'      : pygit2.GIT_STATUS_WT_MODIFIED,\
                             'GIT_STATUS_WT_DELETED'       : pygit2.GIT_STATUS_WT_DELETED,\
                             'GIT_STATUS_WT_TYPECHANGE'    : pygit2.GIT_STATUS_WT_TYPECHANGE,\
                             'GIT_STATUS_WT_RENAMED'       : pygit2.GIT_STATUS_WT_RENAMED,\
                             'GIT_STATUS_WT_UNREADABLE'    : pygit2.GIT_STATUS_WT_UNREADABLE,\
                             'GIT_STATUS_IGNORED'          : pygit2.GIT_STATUS_IGNORED,\
                             'GIT_STATUS_CONFLICTED'       : pygit2.GIT_STATUS_CONFLICTED}
        self.status_flags_value = dict ( (v,k) for k, v in self.status_flags.items() )

        self.find_repos()
        self.grab_latest()


    def grab_latest(self):
        self.repo_flags()
        self.ahead_repos()
        self.diff_repos()
        self.dirty_repos()


    def unpack_flags(self, flags):
        if flags == 0:
            return set(0)
        flag_set = set()
        for flag in sorted(list(self.status_flags_value.keys()))[::-1][:-1]:
            if flags >= flag:
                flags -= flag
                flag_set.add(flag)
        return flag_set


    def flagin(self, flag, check_flags):
        for flag_name in check_flags:
            if flag == self.status_flags[flag_name]:
                return True
        return False


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
        if repo in self.diff:
            flag += '-'
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
        # list_str = id_dent + ' UCP\n'
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


    def repo_flags(self):
        for repo, v in self.repos.items():
            status = v['obj'].status()
            v['fileflags'] = set()
            v['flags'] = set()
            for filepath, flags in status.items():
                flags = self.unpack_flags(flags)
                v['fileflags'].add((filepath, tuple(flags)))
                v['flags'] |= flags
            for flag in v['flags']:
                if self.flagin(flag, self.flagerrors):
                    print("Error", self.flagerrors, flags, filepath, "resolve manually")
                    sys.exit()


    def dirty_repos(self):
        self.dirty = set()
        for repo, v in self.repos.items():
            for flag in v['flags']:
                if self.flagin(flag, self.flagupdate):
                    self.dirty.add(repo)


    def diff_repos(self):
        self.diff = set()
        for repo, v in self.repos.items():
            for flag in v['flags']:
                if self.flagin(flag, self.flagcommit):
                    self.diff.add(repo)


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
            for path, flags in self.repos[repo]['fileflags']:
                for flag in flags:
                    if self.flagin(flag, self.flagupdate):
                        if pygit2.GIT_STATUS_WT_DELETED in flags:
                            index.remove(path)
                        else:
                            index.add(path)
                        break
                index.write()
            return True
        return False


    def git_commit(self, repo, msg):
        if repo in self.diff:
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
        return False


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
    args = parser.parse_args()
    if args.sync:
        args.update = True
        args.commit = True
        args.push = True
    return args


def main():
    args = cli_parse()

    home = Path.home()
    paths = ['scripts', 'configuration', 'development', '.password-store', 'ansible', 'vimwiki']
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
            elif result is not False:
                print(repo, result)
        gitbot.grab_latest()

    if args.push:
        for repo in repos:
            result = gitbot.git_push(repo)
            if result is True:
                print('Pushed', repo)
            elif result is not False:
                print(repo, result)

    sys.exit()


if __name__ == "__main__": main()


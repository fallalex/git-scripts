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
from pygit2 import GitError

class GitStatusBot():

    def __init__(self, paths):
        self.paths = paths
        self.glob_pattern = '/**/.git'
        self.committer = Signature('GitStatusBot', 'gitstat@fallalex.com')
        self.push_user = 'git'
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
                return True
            if cancel is True and selection.lower() in cancel_valid:
                return False


    def match(self, query):
        query = str(query)
        # match all
        if query.lower() == 'all':
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
            result = self.prompt_int_range('Mutiple matches, which one(s)?',
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
            for filepath, flags in status.items():
                if flags != GIT_STATUS_CURRENT:
                    dirt.append(filepath)
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


    def git_add(self, repo):
        if repo in self.dirty:
            repo_obj = self.repos[repo]['obj']
            index = repo_obj.index
            index.read()
            if 'dirt' in self.repos[repo]:
                for path in self.repos[repo]['dirt']:
                    index.add(path)
                index.write()
                return True
        return False


    def git_commit(self, repo, msg):
        if repo in self.dirty:
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
                        help="equivalent to '-acp'")
    parser.add_argument('-a',
                        '--add',
                        action='store_true',
                        help='git add')
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
        args.add == True
        args.commit == True
        args.push == True
    return args

def main():
    args = cli_parse()
    home = Path.home()
    paths = ['scripts', 'configuration', 'development', '.password-store', 'ansible']
    paths = [home / Path(path) for path in paths]
    if args.message is None:
        args.message = 'comitted by gitstat.py'

    gitbot = GitStatusBot(paths)

    if args.list:
        print(gitbot.list_repos())
        sys.exit()

    if args.repo is None:
        print(gitbot.list_repos())
        entry = gitbot.prompt_int_range(
            "Which repo(s)?",
            list(range(1,len(gitbot.repos)+1)))

        if entry is True:
            repos = gitbot.match('all')
        elif entry is False:
            sys.exit()
        else:
            repos = gitbot.match(entry)

    if args.repo:
        repos = gitbot.match(args.repo)

    if not isinstance(repos, list):
        sys.exit()

    if args.add:
        for repo in repos:
            if gitbot.git_add(repo):
                print('Indexed', repo)

    if args.commit:
        for repo in repos:
            result = gitbot.git_commit(repo, args.message)
            if result is True:
                print('Commited', repo)
            elif result is not False:
                print('Error', repo, result)

    if args.push:
        for repo in repos:
            result = gitbot.git_push(repo)
            if result is True:
                print('Pushed', repo)
            elif result is not False:
                print('Error', repo, result)

    sys.exit()
    for k,v in gitbot.dirty.items():
        gitbot.git_add(k)
        if args.message:
            gitbot.git_commit(k, args.message)
        else:
            gitbot.git_commit(k)
        gitbot.git_push(k)
        print(k, v['dirt'])


if __name__ == "__main__": main()


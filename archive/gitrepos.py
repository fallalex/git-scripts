#!/usr/bin/env python3
# List all the repo urls listed in the file github_repos_paginator.py outputs
from pathlib import Path
import json

jsonfile = str(Path.home() / Path('.githubrepos'))
with open(jsonfile, 'r') as f:
    repos = json.loads(f.read())

reposURLs = [x['ssh_url'] for x in repos]
for url in sorted(reposURLs):
    print(url)

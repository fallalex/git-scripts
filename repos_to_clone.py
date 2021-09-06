#!/usr/bin/env python3
# used against output of
#    glab api --paginate groups/cmbu-tvg/projects > cmbu-tvg_projects.json
# use xargs with '-P' to run 'git clone --recursive' on each repo

import json

with open('cmbu-tvg_projects.json', 'r') as f:
    projects_json = json.loads(f.read().replace('}][{','},{'))

# print(json.dumps(projects_json[0]))
for p in projects_json:
    if not p['archived'] and not p['empty_repo']:
        print(p['ssh_url_to_repo'])


#!/usr/bin/env python3
# Stitch all the paginated responses into one json object
from pathlib import Path
import sys,json

pages = sys.stdin.read().strip().split('\n')
singlePage =list()
for page in pages:
    singlePage.extend(json.loads(page))

jsonfile = str(Path.home() / Path('.githubrepos'))
with open(jsonfile, 'w') as f:
    f.write(json.dumps(singlePage))

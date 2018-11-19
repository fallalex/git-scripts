#!/usr/bin/env bash
# $1 is the full path where 'git init' was run
# run after 'git init' 'git add' and 'git commit -m "first commit"'
# after thes commands above the local repo is setup
# now to duplicate it to the server and setup the remote

if [ $# -eq 0 ]
  then
    echo "No arguments supplied"
    exit 1
fi

if [ ! -d "$1" ]
  then
    echo "$1 is not an existing directory"
    exit 1
fi

GIT_URL="git@vcs.fallalex.com:/srv/git/"
REPO_PATH="$(realpath $1)"
REPO_NAME="$(basename $REPO_PATH).git"
BARE_REPO_PATH="$REPO_PATH/$REPO_NAME"

cd $REPO_PATH
git clone --bare $REPO_PATH $BARE_REPO_PATH
scp -r $BARE_REPO_PATH $GIT_URL 
git remote add origin $GIT_URL$REPO_NAME
rm -rf $BARE_REPO_PATH
git fetch origin
git branch -u origin/master

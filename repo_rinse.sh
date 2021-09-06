#!/bin/sh
REPO_DIR=$1
git -C $REPO_DIR clean -xfd
git -C $REPO_DIR submodule foreach --recursive git clean -xfd
git -C $REPO_DIR reset --hard
git -C $REPO_DIR submodule foreach --recursive git reset --hard
git -C $REPO_DIR submodule update --init --recursive

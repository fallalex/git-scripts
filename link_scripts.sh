#!/usr/bin/env bash
# to run this at login add some thing like:
# source "$HOME/scripts/link_scripts.sh"
# Mac is a bear when it comes to standard commands like 'find'
# in the future I should add linux support

mkdir -p $HOME/scripts/.scripts

find $HOME/scripts -type f -perm +u+x | grep -v "/.git/" | xargs -J % ln -fs % $HOME/scripts/.scripts

PATH=$PATH:~/scripts/.scripts

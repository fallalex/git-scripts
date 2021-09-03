The question of how to set up your environment is a big one
one aspect of it is adding personal scripts to $PATH

I wanted to track my personal scripts with GIT but I did not like having them in one Repo
Prefering to setup a heirerachy like this:

tree ~scripts/
scripts/
├── check_ip
│   └── check_ip.py
├── git_scripts
│   └── git_init_remote.sh
├── gpg_scripts
│   ├── backup_gpg_dir.sh
│   ├── create_gpg_tmp.sh
│   ├── remove_gpg_tmp.sh
│   └── revive_gpg_dir.sh
└── otpass
    └── otpass.py

Each directory in '~/scripts' is its own repo. Now how do I add all of the scripts to my $PATH?
Lets shoot to have all personal scripts under the parent '~/scripts/'. To do this lets use symbolic links
to point at executables in the GIT Repos and have the links under '~/scripts/.scripts'.

This script recursivly looks for executables in the 'scripts' directory, avoiding existing executable symbolic links
GIT and symbolic links are not friends, this approach seems like a good compromise.

This script will be sourced by the $SHELL profile running it at login so links stay current. It will add '~/scripts/.scripts' to $PATH


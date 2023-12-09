# List all my private repo urls
# Add the following to /home/git/.bash_profile of my bare git server
function repo_urls () { fd --base-directory=/srv/git -uue git -x readlink -f | xargs -L1 -I '$' echo 'git@git.fallalex.com:$'; }
repo_urls

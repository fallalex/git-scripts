for repo in $(fd -t d '\.git$' -uu -x dirname)
do
  [[ -z $(git -C $repo status -s) ]] || echo "$repo"
done


# Author a policy

__SUB__

__NOSCRIPT__

## The interview

__KIND_LINES__

The name becomes a `my-` id (`my-block-secrets`): lowercase letters, digits and hyphens. The answers fill the chock policy templates copied from engine commit `__ENGINE_COMMIT_12__`. A "Review the files" view shows every generated file and takes direct edits that win over the answers.

## Catalog policies

Picked catalog policies install beside the authored one. They are the same policies as the builder's, and a share link carries the agent and catalog policy ids only, and never the draft. Drafts live in the browser's localStorage and never leave it.

## The setup script

__SCRIPT_HINT__ The script:

1. Asks for the agent (one of the five client ids), the folder, and build-only or install, with the interview's answers as defaults.
2. Writes `chock.selection.yaml` (schema 2) and the policy folder into `.agents/policies/<id>/` as quoted heredocs.
3. Runs `chock check --repo <folder> --only validate,evals` and stops on any failure.
4. Runs `chock install --selection <folder>/chock.selection.yaml --client <agent> --trust-local <id>=<sha256>`, the step the CLI asks you to review. The sha256 pins exactly the policy code printed in the script, so reading the script is that review. Answering `install` also passes `--apply`, the agent's own install step, but only where a person has seen that step work live.

The page never compiles a policy or runs generated code. The script never pipes anything from the network into a shell. Its only network call is chock's own pinned catalog fetch when catalog policies are picked.

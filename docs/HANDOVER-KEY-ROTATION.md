# HANDOVER: Nostr Key Rotation — Compromised npub

## Situation

The npub `npub12m5exm2uk3xa674cc5r0hlyvccs5xxn7qv83ezuteefv5972nquq4j4szl` is compromised. The corresponding nsec (private key) is:

`nsec1gszj7vzu56wjxk0kaja4tc3n8p4xachjev7maev4w82a8xd69ddsm7t63e`

This key is used for ALL ngit (nostr git) operations across all repos.

## What Needs to Happen

1. Generate a new nostr keypair (new nsec + npub)
2. Update `~/scripts/ngit-tool.sh` — replace the NSEC variable
3. Update ALL git remotes in ALL repos that reference the old npub
4. Re-initialize ngit repos with the new key (ngit init)
5. Push all branches with the new key
6. Scrub the old nsec from shell history, scripts, and any config files

## Affected Repos (7 total)

### Balloon repos (all use same fork remote):
- `~/repos/balloon-fresh` — 4 remotes
- `~/worktrees/balloon-speed-tests` — 4 remotes
- `~/worktrees/balloon-range-tests` — 4 remotes
- `~/worktrees/balloon-circuit-design` — 4 remotes
- `~/worktrees/balloon-tollgate` — 6 remotes (also has orangesync relay)

### Other repos:
- `~/repos/physical-router-test-automation` — 2 remotes
- `~/repos/tollgate-zitadelle-slides` — 2 remotes

### Remote URL pattern:
```
nostr://npub12m5exm2uk3xa674cc5r0hlyvccs5xxn7qv83ezuteefv5972nquq4j4szl/relay.ngit.dev/<repo-name>
```

Replace `npub12m5exm2...` with the new npub in all remote URLs.

## Key Location (NOT in git — safe)

The nsec is hardcoded in:
- `~/scripts/ngit-tool.sh` line ~10: `NSEC="${NSEC:-nsec1gszj7...}"`

This file is NOT in a git repo. No nsec appears in any git commit history or tracked file.

## Additional Security Issue

The balloon-fips worktree has a GitHub PAT hardcoded in its git remote URL:
```
https://felixfelix-bot:ghp_c5...RZji@github.com/felixfelix-bot/microfips.git
```
This token should also be rotated and moved to a credential helper or SSH key.

## Git Secret Detection Hooks

There are currently NO git pre-commit/pre-push hooks for secret detection. The `git-secret-detection-hooks` skill exists but is not installed globally. Recommend installing:

```bash
# Install global git hooks for secret detection
cp ~/.hermes/profiles/manager/skills/git-secret-detection-hooks/scripts/pre-commit ~/.git-templates/hooks/
cp ~/.hermes/profiles/manager/skills/git-secret-detection-hooks/scripts/pre-push ~/.git-templates/hooks/
git config --global init.templatedir ~/.git-templates
git config --global core.hooksPath ~/.git-templates/hooks
```

This would block any future accidental commits containing nsec1..., npub1..., ghp_..., etc.

## Steps for Key Rotation

```bash
# 1. Generate new key
nak key generate  # outputs new nsec + npub

# 2. Update ngit-tool.sh
# Replace NSEC value with new nsec

# 3. Update all remotes (example for one repo)
cd ~/repos/balloon-fresh
for remote in origin fork; do
  OLD_URL=$(git remote get-url $remote)
  NEW_URL=$(echo $OLD_URL | sed 's/npub12m5exm2uk3xa674cc5r0hlyvccs5xxn7qv83ezuteefv5972nquq4j4szl/<NEW_NPUB>/')
  git remote set-url $remote "$NEW_URL"
done

# 4. Re-init ngit with new key
NSEC=<new_nsec> ~/scripts/ngit-tool.sh init ~/repos/balloon-fresh esp32-balloon-integration-fresh-fork

# 5. Push all branches
for repo in ~/repos/balloon-fresh ~/worktrees/balloon-*; do
  cd $repo
  git push --all fork
done

# 6. Scrub old key from history
history -d $(history | grep -n "nsec1gszj7" | tail -1 | cut -d' ' -f1)
```

## Context

This handover is from the balloon-hermes orchestrator. The balloon project work continues unaffected — all commits are already pushed. The key rotation is a security task that should not interrupt the characterization walk planned for tomorrow morning.
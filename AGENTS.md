# Rules for agents in this repo

This is a public library. It is part of a larger private project whose
rules live in `flewber/sorting_machine_planning` (`AGENTS.md`). An agent
with access to that repo reads it first.

- **Clean side.** Nothing about how any existing sorting machine's
  boards or software work may enter this repo. Never read or copy
  another project's source.
- **Public.** Nothing private about the owner's machine or plans goes in
  code, comments, commits or pull requests.
- Work on a branch and open a pull request. Say what was tested and how.
- `uv run pytest` must pass before a pull request is opened and before
  it is merged.
- No secrets or credentials. `keys.py` is ignored on purpose.
- "Brick", not "lego", in any new name.
- No em-dashes in text written for the owner.

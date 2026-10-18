# Rules for working on this repository

## Thumb rule: trial after every push (owner's standing instruction, 2026-10-19)
1. After every push to main, wait for the Render deploy to show "live" (list_deploys).
2. Run `python scripts/post_push_trial.py`. It sends the standard requests through routing, job, approval, PDF and Excel and must print PASS for every case.
3. Any new or changed request type, command or sample text given to the owner must first be run through this pipeline. Add a case to `scripts/post_push_trial.py` for it.
4. Report to the owner what the trial showed, and clearly separate what was verified from what was not (for example live Render behaviour, AI vision reading).
5. Never hand over a command or claim something works without having run it.

## Other standing rules
- Client-facing PDF/Excel never show calculation basis (recipes, factors, norms, method notes).
- Commit trailers: Co-Authored-By and Claude-Session lines as given by the session.

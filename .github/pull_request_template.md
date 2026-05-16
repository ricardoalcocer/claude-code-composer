## What this changes

<!-- One or two sentences. -->

## Why

<!-- The motivation. If you're adding a new style pack, chord quality, feel pattern, drum
pattern, or transition idiom, mention the touchstone artist or idiom. -->

## Type of change

<!-- Check what applies. -->

- [ ] Bug fix in `composer.py` (mechanical — wrong MIDI, wrong .RPP, parse error, etc.)
- [ ] New chord quality / feel pattern / chugg pattern / drum pattern
- [ ] New style pack or transition idiom (touches `SKILL.md` — the AI's prompt)
- [ ] Other `SKILL.md` edit (changes how the skill *thinks*, not just what it can do)
- [ ] Breadcrumb / spec format change (touches the EXTSTATE block, NOTES structure, or spec.json shape — see CONTRIBUTING.md)
- [ ] Docs / README / typos
- [ ] Other

## How I tested

<!-- E.g. "Composed `tests/spec_em_rock.json` before and after, listened in Reaper, items
land on the right tracks at the right beats." For prompt edits, paste a before/after of
what the skill produces given the same brief. -->

## Checklist

- [ ] I ran my change end-to-end (compose or analyze+fill) and verified the output in Reaper
- [ ] No `config.json` or `style.md` in the diff (`git status` is clean)
- [ ] If I touched `SKILL.md`, the PR description has a before/after of what the skill produces
- [ ] If I changed the breadcrumb format, older projects still work via the 4-tier resolution chain

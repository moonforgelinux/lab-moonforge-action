# lab-moonforge-action

A GitHub action that runs a test suite from a [Moonforge](https://github.com/moonforgelinux/meta-moonforge) checkout, in a container carrying its own Python stack, and optionally wraps that run in the [dut-control](https://github.com/psaavedra/dut-control) lab lifecycle: reserve a device, flash it, wait for it to boot, test, wipe it, hand it back.

> [!NOTE]
> Under construction, landing feature by feature.

## Developing

```sh
python3 -m venv .venv && . .venv/bin/activate
pip install -e '.[test,lint]'

pytest                                # unit and lifecycle tests, no container
./.github/scripts/run-all-sanatizers  # radon, pycodestyle, pyflakes, shellcheck, commits
```

## Legal

MIT License

Copyright (c) 2026 Igalia, S.L.

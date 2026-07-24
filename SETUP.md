# Setup

The profile README is a pair of SVGs regenerated every morning by GitHub
Actions. `README.md` just points at them.

## One-time setup

1. Create the repo `harryitc/harryitc` on GitHub. The name has to match your
   username — that is what makes its README show on your profile page.
2. Create a Personal Access Token (classic) at
   <https://github.com/settings/tokens> with the `repo` and `read:user` scopes.
3. Add it under `Settings → Secrets and variables → Actions → New repository
   secret`, named `ACCESS_TOKEN`.
4. Push this directory to the repo's `master` branch. The workflow runs on push,
   so the first render happens immediately.

Never paste the token into a file, a commit, or a chat. It only ever lives in
the repo secret and in `${{ secrets.ACCESS_TOKEN }}`.

## Changing the text

Everything hand-written lives in `profile_config.py` — sections, labels, values,
your birthday, and the repos to leave out of the line count. Live numbers are
filled in by `today.py`.

Check a change without touching the API:

```sh
python today.py --offline    # zeroed stats, real layout
```

Check it against real data (token in the environment, not in a file):

```sh
ACCESS_TOKEN=ghp_... python today.py
```

## Changing the picture

Drop a new photo in as `avatar.jpg`, then:

```sh
python generate_ascii.py --crop LEFT,TOP,RIGHT,BOTTOM --invert --floor 95
```

- `--crop` takes source pixel coordinates. Crop tight to head and shoulders.
- `--invert` when the subject is darker than the background.
- `--floor` blanks anything dimmer than the given brightness (0–255). Raise it
  until the background disappears; lower it if the subject starts eroding.
- `--width` defaults to 46 characters. The SVG resizes to fit whatever you pick.

A portrait on a plain background needs almost no tuning. A busy photo will
always leave some speckle — open `ascii_art.txt` and delete the stray
characters by hand. That file is the source of truth; the photo is only ever
used to produce it.

## How the daily run works

`.github/workflows/main.yml` runs at 23:00 UTC (06:00 ICT), renders both SVGs,
and commits them only if they changed.

Walking every commit in every repo to total up added and deleted lines is the
slow part, so results are cached per repo in `cache/loc.json`, keyed on the
repo's commit count. That file is committed on purpose — deleting it just makes
the next run slower, not wrong.

If the API call fails, the script exits non-zero and leaves the existing SVGs
alone, so a bad run shows up as a red check rather than a blank profile.

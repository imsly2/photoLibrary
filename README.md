# Library

A local photo and video library for a Windows PC. Copy this folder onto a
drive, run Setup once, then open Library each day. There is no installer
and no MSI.

Browse by **People**, **Places**, and **Tags**. Switch the header
**Language** menu to **中文**. Optional offline AI can group faces, label
objects, and name GPS places when those models are installed on this
computer.

Photos stay files on the PC. The app does not upload them, and you do
not need a cloud account to browse.

## Who it is for

Family PCs. Someone can set it up; a parent or mother-in-law can browse
afterward. Daily use is a double-click, then the browser on this
computer.

It is not a cloud host and not an editor. It does not rearrange your
originals unless you ask it to copy a folder here.

Pictures still on an iPhone are copied from inside Library. Click
**Import iPhone**. The phone program is in this same folder at
`tools/iphone`. Unlock the phone and tap Trust, pick a folder on the
PC, then **Look** and **Copy what's missing**. An existing file is
never replaced. The phone is read-only. When the copy finishes, that
folder is added to the library.

## Quick start

1. **Get the folder.** Clone this repo over HTTPS, or download the ZIP
   and unzip it somewhere on the PC. No GitHub account.
2. **Setup once.** Double-click `Setup.bat`. That needs the internet
   (Python, ffmpeg, optional git, and optional face / object / place
   models). Models stay in `library-data/`. Setup also writes a Desktop
   / Start Menu **Library** icon (`CreateShortcut.bat` can recreate it).
   If the iPhone helper needs it, Setup installs the .NET 10 runtime.
   Open Apple Devices (or iTunes) once on that PC before plugging in a
   phone. If a step fails, the window says what to try next. Safe to run
   again.
3. **Library daily.** Double-click the **Library** icon (or `Library.bat`).
   A browser window opens on this computer.
4. **Chinese UI.** In the header, set **Language** to **中文**. The
   choice is remembered.
5. **Add photos.** Click **Add folder** and point it at pictures already
   on the PC. You can copy them into the library, or leave them where
   they are.
6. **Updates.** **Update Library** in the header, or `Update.bat`. That
   always tracks `main`: plain `git` over public HTTPS if git is
   present, otherwise a zip of `main`. `library-data/` is not replaced.
   If Library was open, it restarts. No GitHub login. Do not install
   GitHub CLI (`gh`). After an update, run `Setup.bat` again only if
   new local models were added.

`Setup.bat -Help` prints that story. `Setup.bat -DryRun` probes without
downloading.

To put a lean copy on a USB stick or another PC, double-click
`PackDeploy.bat` in this folder. It writes `dist/photoLibrary-deploy.zip`
and overwrites that file if you run it again. Copy the zip, extract it,
then run `Setup.bat` on that PC. The zip is the app only -- your photos,
`library-data/`, and `.venv` stay behind.

## Requirements

- **Windows.** This is the family-PC path. `Library.bat` / `Setup.bat`
  are the launchers.
- **Internet** for Setup and the first model download. After that,
  browsing and the local models run offline.
- **No GitHub account** once the repo is public. Clone over HTTPS, or
  download the ZIP. Do not install GitHub CLI (`gh`). A GitHub account
  is only needed if you want to open issues or send a pull request.

This repo must stay **public** so a family PC can fetch `main` without
logging in. A ZIP copy can still **Update Library** (it downloads the
latest `main` zip and overlays files; `library-data/` stays).

## Privacy

Pictures and videos stay on this PC. The catalog, previews, optional
models, and (if you chose copy) originals live under `library-data/`
next to the app. The app never uploads your photos.

Face, object, and place workers run on this computer when installed.
They do not call a cloud API. Browse still works if those models are
missing.

The server listens on `127.0.0.1` by default, so only this computer can
open it.

## Status

Early and taste-driven. It is useful on a family PC today, but this is
not a polished product guarantee. Things still change as the chrome is
shaped.

## Docs

The files under `docs/` are the build notes: what the library is meant
to do, what has been checked, and how screens should behave.

| File | What it is |
|------|------------|
| [docs/PRODUCT.md](docs/PRODUCT.md) | The product: features and the check for each |
| [docs/STATUS.md](docs/STATUS.md) | What has actually been verified |
| [docs/UI-SPEC.md](docs/UI-SPEC.md) | Screen contract for the Windows shell |
| [docs/CONVENTIONS.md](docs/CONVENTIONS.md) | Defaults taken from other photo apps |

## Developing from two Windows PCs

Use a separate clone on each PC. Keep personal photos outside the repository;
`library-data/`, `.venv/`, and `.env` files are ignored. Configure Git's credential
manager for HTTPS login; never put tokens in a remote URL or tracked file. Confirm
`git config user.name` and `git config user.email` belong to the person committing.
The repository owner can invite the second account under GitHub Settings >
Collaborators; that account must accept the invitation before pushing.

Before new work, with a clean working tree:

```powershell
git switch main
git fetch origin
git pull --ff-only origin main
git switch -c feature/my-change
```

Make a small change, review `git diff`, stage named files, then:

```powershell
git commit -m "Describe the change"
git push -u origin feature/my-change
```

Open the branch's Compare & pull request link on GitHub, targeting `main`.
Review the diff and checks on either PC, merge on GitHub, then update the other
PC with fetch and fast-forward pull. Commit or stash local work before switching
branches. Do not force-push. The app's Update Library button follows `main`;
use Git commands while developing on a feature branch.

### Second-PC troubleshooting

- Missing ffmpeg: Setup uses winget package `Gyan.FFmpeg`. Restart the launcher
  after installation so it sees the updated PATH. Video/HEIC previews require
  a working media decoder; a running web server alone does not verify them.
- Missing phone runtime: the bundled Windows x64 helper requires the .NET 10
  runtime (`Microsoft.DotNet.Runtime.10`). It is not self-contained. Setup recognizes
  both "install .NET" and "install or update .NET" host messages.
- Apple USB: install/open Apple Devices or iTunes, connect by USB, unlock, and
  tap Trust. Restricted sessions may not be able to inspect Store apps or devices;
  failed inspection does not prove that the phone is absent.
- Python environment creation: if ensurepip fails in a restricted temporary
  directory, use a writable TEMP/TMP directory for that setup session and rerun.
- Optional model packs are downloaded separately by Setup; successful core
  installation does not mean all optional AI dependencies work on that Python.

Before a full phone backup, use a separate small test destination and verify
original file bytes and metadata. The importer matches existing files by name
and size, not content checksum: a skip is not proof of identical content. Keep
Live Photo stills and motion files together. Interrupted copies use partial files
and size checks. Phone pulls temporarily stage a whole file on the system drive,
so both that drive and the destination need free space. iCloud-only originals
cannot be verified by a DCIM inventory. Never report a complete backup from
transfer counts alone.

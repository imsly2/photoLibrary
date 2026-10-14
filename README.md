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

It is not a phone copier, not a cloud host, and not an editor. It does
not rearrange your originals unless you ask it to copy a folder here.

## Quick start

1. **Get the folder.** Clone this repo over HTTPS, or download the ZIP
   and unzip it somewhere on the PC. No GitHub account.
2. **Setup once.** Double-click `Setup.bat`. That needs the internet
   (Python, ffmpeg, optional git, and optional face / object / place
   models). Models stay in `library-data/`. Setup also writes a Desktop
   / Start Menu **Library** icon (`CreateShortcut.bat` can recreate it).
   If a step fails, the window says what to try next. Safe to run again.
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

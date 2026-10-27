# iPhone photos — help

A read-only copy of the iPhone camera roll onto a Windows PC over USB. It uses Apple's file channel (AFC), the same family iTunes uses. It does not use Explorer's camera view.

## What a finished run does

- Copies every file under the phone's `/DCIM/` (photos, videos, Live Photos, screenshots, screen recordings) into a folder you name.
- Puts them in `YYYY-MM` folders by capture date.
- Writes `get-and-see.db` and `summary.txt` in that folder. The database is the list of files that copied successfully. `summary.txt` is the readable version.
- On the next run of the same command, skips every file the database already marks done.

The phone is read-only. The program has no delete, move, or write path against the device.

## The window

On a new Windows PC, double-click `Setup.bat` in this folder once. It installs Python 3.12+ (the window), the .NET 10 runtime (the phone helper), and the Apple Devices app when those are missing. It builds the phone helper if that program is not already in the folder. It does not copy photos. Then open the window with `Launch-Window.ps1` in this folder. That is the way to run a copy.

The window shows the connected phone by name. A folder button picks the destination. It remembers the last folder. **Look** lists three counts before anything is copied:

- On the phone
- Exact match, will skip (same filename and same size already in the folder)
- Will copy

The list under the counts is one row per phone file. It shows the phone path and size, and what the folder scan found:

- Exact match: the relative path inside the folder and that same size. Status: Skipped, exact match.
- Same filename, different size: the folder path, the folder size, and the phone size, side by side. Status: Will copy, size differs.
- Same filename and same size, but that folder file is already paired to another phone file: the folder path and both sizes. Status: Will copy, already paired. One folder file satisfies only one phone file, so this one still copies.
- No file with that exact name: "not in this folder", plus the folder path of a same-stem file when one exists (for example `IMG_0140.JPG` when the phone file is `IMG_0140.HEIC`). A same-stem file is not a match.

The scan walks the whole destination, including every subfolder. A match is the filename and the byte size together. A JPEG does not count as the HEIC of the same shot.

While a copy runs, the status on that row changes to Copying, then Copied plus the path it landed in. Skipped rows stay Skipped, exact match.
**Copy what's missing** copies only the files that are not an exact match. Each success is appended to `iphone-photos-log.jsonl` in the destination folder as soon as that file finishes, so a stopped run can continue. Escape stops the run. Files already copied stay copied. Closing the window mid-copy is the same as Escape.

A file that is already in the folder is never replaced. Same name and same size is an exact match and is skipped. Same name and a different size gets a new file beside the old one: `IMG_0140_2.JPG` next to `IMG_0140.JPG`. The old bytes stay put. Choosing per file is later.

`get-and-see.exe` remains the command-line preview (`copy --dry-run`). It does not know about files copied before its own log existed, so the window is what you use against `E:\iPhone14_8-27-2026`.

## How you run it

1. Copy this folder onto the PC. Double-click `Setup.bat` once. It installs what the window needs: Python 3.12+ with tkinter, the .NET 10 runtime, and Apple Devices when the USB driver is missing. The window itself has no pip packages. `requirements.txt` is not part of the run. `Setup.bat -DryRun` only prints what it would install.
2. If you use the Store app, open Apple Devices once after a reboot so the USB service is listening. iTunes already running covers the same service.
3. Plug in the iPhone, unlock it, tap Trust This Computer once on that PC.
4. Open the window with `Launch-Window.ps1` in this folder.

Unlock the phone and leave it awake. Choose the folder (the window starts on the last folder you used). Press **Look**, read the exact-match skips, then **Copy what's missing**.

`get-and-see.exe copy --dest "E:\iPhone14_8-27-2026" --dry-run` only previews the phone. It lists every camera-roll file and does not skip the copies already on E:.

## What the copy includes

Files physically stored in the camera roll. Original filenames and EXIF stay intact.

Albums, favorites, and face tags stay on the phone. They live in Apple's photo database, not in the image files.

If Settings → Photos → Optimize iPhone Storage is on, many full-size originals are in iCloud and are not on the phone to copy. Switch to Download and Keep Originals and wait for the download to finish first.

## Resume, including files copied before this program

The database skips a file only when this program has marked it done, identified by the path on the phone plus the size in bytes.

Files copied earlier with Explorer are not in that database. Pointing `--dest` at that older folder does not make the program treat them as done. It would copy them again. An existing file is never overwritten. When the name is already taken, the new file is written beside it (`_2`, `_3`, …). The first use against an existing pile is a dry run, then a match of old filenames and sizes into the database, then a real copy of what is still missing.

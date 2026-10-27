# iPhone photos

Adopted tool for pulling the iPhone camera roll onto a PC over USB, with a log of what landed and a way to resume.

The program is [get-and-see](https://github.com/denis-a-evdokimov/get-and-see) v1.1.0. We did not write it. This folder is where it lives in slyOS, and where the run notes live. The pictures themselves stay on a drive you choose later.

| Read | For |
|------|-----|
| [docs/PRODUCT.md](docs/PRODUCT.md) | What it does and how a run works |
| [docs/STATUS.md](docs/STATUS.md) | What is true on this machine right now |
| [TRAPS.md](TRAPS.md) | The old-copies problem, iCloud, and the USB driver |

On a new PC, run `Setup.bat` in this folder once. Then open the window with `Launch-Window.ps1`.

The command-line preview is a single file and does not need .NET. The window's phone helper does. `Setup.bat` installs that runtime.

```powershell
bin\get-and-see.exe copy --dest "D:\YourFolder" --dry-run
```

`--dry-run` lists what it would copy and writes nothing. Leave `--dest` unset until Steve picks the folder.

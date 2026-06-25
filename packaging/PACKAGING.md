# OrbitDeck — Native Packaging Guide

This guide builds **native distribution packages** so OrbitDeck installs with the
system package manager and shows up in the application menu. It covers:

- [Debian / Ubuntu `.deb`](#debian--ubuntu-deb)
- [Fedora / RHEL `.rpm`](#fedora--rhel-rpm)
- [Arch Linux package](#arch-linux-package)
- [AppImage](#appimage-distro-agnostic)
- [Flatpak](#flatpak-distro-agnostic)

These produce packages that depend on the **distro's** Python packages
(matplotlib, numpy, tkinter). For a self-contained bundle that needs no system
Python at all, use the [PyInstaller build](BUILD.md) instead.

> **The full optional set is included by default.** Every packaging route here
> pulls in `sgp4`, `cartopy`, and `openpyxl` as well as the required packages —
> as `Recommends` (deb/rpm, installed by default), `optdepends` (Arch), or
> bundled modules (AppImage/Flatpak/PyInstaller `[full]`) — so a normal install
> gets the C-accelerated propagator, high-resolution coastlines, and native
> `.xlsx` export.

Helper files referenced below live in this `packaging/` directory:

| File | Purpose |
|---|---|
| `orbitdeck.desktop` | Freedesktop menu launcher |
| `io.github.prstoetzer.OrbitDeck.metainfo.xml` | AppStream metadata (software centers) |
| `PKGBUILD` | Arch package recipe (tagged **release**) |
| `.SRCINFO` | AUR metadata for `PKGBUILD` (regenerate before pushing) |
| `PKGBUILD-git` | Arch recipe for the `orbitdeck-git` AUR package (latest **git `HEAD`**) |
| `.SRCINFO-git` | AUR metadata for `PKGBUILD-git` |
| `orbitdeck.spec.rpm` | RPM spec |
| `debian/` | Debian packaging tree (`control`, `rules`, `changelog`, `source/`) |

> Keep the version in each helper in sync with `orbitdeck/__init__.py`. A
> release tag `vX.Y.Z` is assumed where a source tarball is fetched. For AUR
> submission specifics, see [Submitting to the AUR](#submitting-to-the-aur).

---

## Debian / Ubuntu (`.deb`)

### Install the build tools

```bash
sudo apt update
sudo apt install devscripts debhelper dh-python python3-all \
                 python3-setuptools pybuild-plugin-pyproject
```

### Build

```bash
# from the repo root
cp -r packaging/debian .          # put the packaging tree where dpkg expects it
dpkg-buildpackage -us -uc -b      # -b = binary only, unsigned
```

The `.deb` is written to the **parent** directory. Install and run:

```bash
sudo apt install ../orbitdeck_0.36.10-1_all.deb   # pulls deps + the full optional set
orbitdeck
```

The package depends on `python3-tk`, `python3-matplotlib`, `python3-numpy`, and
`python3-certifi`, and **recommends the full optional set** — `python3-sgp4`,
`python3-cartopy`, and `python3-openpyxl` — which `apt` installs by default
(unless you pass `--no-install-recommends`), so a normal install gets the
C-accelerated propagator, high-resolution coastlines, and native `.xlsx` export.

> The provided `debian/source/format` is `3.0 (native)`, which is simplest for
> in-tree builds. For an official upload to a Debian/Ubuntu archive you'd switch
> to `3.0 (quilt)` with a separate upstream tarball and a signed `.changes`.

---

## Fedora / RHEL (`.rpm`)

### Install the build tools

```bash
sudo dnf install rpm-build rpmdevtools python3-devel python3-setuptools \
                 python3-wheel python3-pip
rpmdev-setuptree                  # creates ~/rpmbuild/{SOURCES,SPECS,...}
```

### Build

```bash
# from the repo root: create the source tarball the spec expects
git archive --format=tar.gz --prefix=OrbitDeck-0.36.10/ \
    -o ~/rpmbuild/SOURCES/orbitdeck-0.36.10.tar.gz v0.36.10

rpmbuild -ba packaging/orbitdeck.spec.rpm
```

The binary RPM lands in `~/rpmbuild/RPMS/noarch/`. Install and run:

```bash
sudo dnf install ~/rpmbuild/RPMS/noarch/orbitdeck-0.36.10-1.*.noarch.rpm
orbitdeck
```

It requires `python3-tkinter`, `python3-matplotlib`, `python3-numpy`,
`python3-certifi`, and **recommends the full optional set** (`python3-sgp4`,
`python3-cartopy`, `python3-openpyxl`), which dnf installs by default with weak
dependencies enabled.

> Building from a local checkout instead of a tag? Just tar the working tree
> with the matching `OrbitDeck-<version>/` prefix into
> `~/rpmbuild/SOURCES/orbitdeck-<version>.tar.gz`.

---

## Arch Linux package

### Build with `makepkg`

```bash
# from the repo root
cp packaging/PKGBUILD .
makepkg -si                       # build + install, pulling dependencies
orbitdeck
```

`makepkg` produces `orbitdeck-0.36.10-1-any.pkg.tar.zst`. The recipe pulls
`tk`, `python-matplotlib`, `python-numpy`, and `python-certifi` as hard
dependencies, and lists `python-sgp4` / `python-cartopy` / `python-openpyxl` as
`optdepends`. On Arch, optdepends are **not** auto-installed, so to get the full
optional set install them alongside the package:

```bash
sudo pacman -S python-sgp4 python-cartopy python-openpyxl
```

(Or, for a build that always carries them, move those three from `optdepends`
into `depends` in the `PKGBUILD`.)

> The default `PKGBUILD` fetches the release tarball for tag `v$pkgver` and uses
> `sha256sums=('SKIP')`. For a real AUR submission, replace `SKIP` with the
> actual checksum (`updpkgsums`) and add a `.SRCINFO` (`makepkg --printsrcinfo
> > .SRCINFO`). To build straight from a **local checkout**, point `source=()`
> at the working tree or use the `orbitdeck-git` recipe (below).

---

## Submitting to the AUR

The [Arch User Repository](https://aur.archlinux.org) hosts the **recipe**
(`PKGBUILD` + `.SRCINFO`), not a built package — users build it themselves with
`makepkg` or an AUR helper. This repo ships everything you need:

| File | AUR package | Builds |
|---|---|---|
| `packaging/PKGBUILD` + `packaging/.SRCINFO` | `orbitdeck` | the latest tagged **release** |
| `packaging/PKGBUILD-git` + `packaging/.SRCINFO-git` | `orbitdeck-git` | the latest **git `HEAD`** |

> In an AUR git repo the recipe file must be named exactly **`PKGBUILD`** and the
> metadata **`.SRCINFO`**. The `-git` suffixes here only distinguish the two
> variants inside this source tree — drop them when you copy the files across.

### 1. One-time account setup

1. Create an account at <https://aur.archlinux.org>.
2. Add your **SSH public key** under *My Account → SSH Public Key* (AUR pushes go
   over SSH). Generate one if needed:
   ```bash
   ssh-keygen -t ed25519 -C "aur"
   cat ~/.ssh/id_ed25519.pub      # paste into the AUR profile
   ```
3. Check access: `ssh aur@aur.archlinux.org help`

### 2. Prepare the release recipe (`orbitdeck`)

The shipped `.SRCINFO` carries `sha256sums = SKIP`, which is fine for a local
build but **not** for the AUR — fill in the real checksum first. This needs the
`v$pkgver` tag to already be pushed to GitHub (the `source=` URL points at it),
and `pacman-contrib` + `namcap` installed (`sudo pacman -S pacman-contrib namcap`).

```bash
cp packaging/PKGBUILD .
updpkgsums                          # downloads the tagged tarball, fills sha256sums
makepkg --printsrcinfo > .SRCINFO   # regenerate to match
namcap PKGBUILD                     # lint the recipe
makepkg -si                         # smoke-test the build locally
```

(The `packaging/.SRCINFO` in the repo is provided so you can diff against your
generated one; always commit the freshly generated file.)

### 3. Prepare the git recipe (`orbitdeck-git`)

The VCS package pins by commit, so it keeps `sha256sums=('SKIP')` and derives the
version with a `pkgver()` function — no checksum step:

```bash
cp packaging/PKGBUILD-git ./PKGBUILD
makepkg --printsrcinfo > .SRCINFO   # pkgver is filled in from `git describe`
makepkg -si                         # smoke-test (clones the repo, builds HEAD)
```

### 4. Clone the AUR repo and push

The AUR repo is created on first push. Use the package name as the repo name:

```bash
git clone ssh://aur@aur.archlinux.org/orbitdeck.git aur-orbitdeck
cd aur-orbitdeck
cp /path/to/PKGBUILD /path/to/.SRCINFO .   # ONLY these (plus any .install)
git add PKGBUILD .SRCINFO
git commit -m "Initial import: orbitdeck 0.36.10-1"
git push
```

Repeat with `ssh://aur@aur.archlinux.org/orbitdeck-git.git` for the git variant.
The package then appears at `https://aur.archlinux.org/packages/orbitdeck`.

### 5. Updating on a new release

```bash
# in the aur-orbitdeck checkout:
# 1. bump pkgver (reset pkgrel=1) in PKGBUILD  — git variant updates itself
# 2. refresh checksum + metadata
updpkgsums
makepkg --printsrcinfo > .SRCINFO
# 3. commit + push
git commit -am "Update to 0.36.10-1"
git push
```

Bump `pkgrel` (not `pkgver`) when only the packaging changes. Regenerate
`.SRCINFO` on **every** change — the AUR rejects a push whose `.SRCINFO` is out
of date.

### Notes

- The AUR git repo holds **only** the recipe — never the source tree, the built
  package, or `src/`/`pkg/` directories.
- The `v0.36.10` **tag must be live and public on GitHub** or `updpkgsums` and
  users' builds will 404 on the `source=` URL.
- `arch=('any')` is correct (pure-Python / noarch): one package serves every
  architecture.
- `optdepends` are not auto-installed on Arch; the full optional set
  (`python-sgp4` / `python-cartopy` / `python-openpyxl`) is opt-in, as described
  above.

---

## AppImage (distro-agnostic)

An AppImage is a single executable that runs on most Linux distributions. The
simplest route reuses the [PyInstaller one-folder build](BUILD.md) as the
AppDir payload:

```bash
# 1. produce the standalone bundle
pip install pyinstaller && pip install -e ".[full]"
pyinstaller orbitdeck.spec            # -> dist/OrbitDeck/

# 2. lay out an AppDir
mkdir -p OrbitDeck.AppDir/usr/bin
cp -r dist/OrbitDeck/* OrbitDeck.AppDir/usr/bin/
cp packaging/orbitdeck.desktop OrbitDeck.AppDir/orbitdeck.desktop
cp orbitdeck/gui/assets/icon-256.png OrbitDeck.AppDir/orbitdeck.png
ln -s usr/bin/OrbitDeck OrbitDeck.AppDir/AArun       # AppRun entrypoint
# (rename the symlink target to your bundle's launcher; see appimagetool docs)

# 3. package it
wget -O appimagetool https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
chmod +x appimagetool
./appimagetool OrbitDeck.AppDir OrbitDeck-x86_64.AppImage
```

Because the payload is a PyInstaller bundle, the AppImage carries its own Python
and needs nothing from the host. Build on the **oldest** distro you want to
support (glibc compatibility is forward-only).

---

## Flatpak (distro-agnostic)

A Flatpak manifest builds OrbitDeck and its Python dependencies against a
runtime. Sketch (`io.github.prstoetzer.OrbitDeck.yaml`):

```yaml
app-id: io.github.prstoetzer.OrbitDeck
runtime: org.freedesktop.Platform
runtime-version: '23.08'
sdk: org.freedesktop.Sdk
command: orbitdeck
finish-args:
  - --share=network          # live GP / transponder / space-wx fetches
  - --share=ipc
  - --socket=fallback-x11
  - --socket=wayland
  - --device=dri
  - --filesystem=home        # save printable PDFs / CSV exports, ~/.orbitdeck
modules:
  # Required: matplotlib, numpy, certifi. Plus the full optional set — sgp4,
  # cartopy, openpyxl — so the Flatpak ships with the C-accelerated propagator,
  # high-resolution coastlines, and native xlsx export. Then OrbitDeck itself:
  - name: orbitdeck
    buildsystem: simple
    build-commands:
      - pip3 install --prefix=/app --no-deps .
      - install -Dm644 packaging/orbitdeck.desktop /app/share/applications/io.github.prstoetzer.OrbitDeck.desktop
      - install -Dm644 orbitdeck/gui/assets/icon-256.png /app/share/icons/hicolor/256x256/apps/io.github.prstoetzer.OrbitDeck.png
      - install -Dm644 packaging/io.github.prstoetzer.OrbitDeck.metainfo.xml /app/share/metainfo/io.github.prstoetzer.OrbitDeck.metainfo.xml
    sources:
      - type: dir
        path: .
```

Build and install locally:

```bash
flatpak install flathub org.freedesktop.Platform//23.08 org.freedesktop.Sdk//23.08
flatpak-builder --user --install --force-clean build-dir \
    io.github.prstoetzer.OrbitDeck.yaml
flatpak run io.github.prstoetzer.OrbitDeck
```

Generate the pinned dependency modules with
[`flatpak-pip-generator`](https://github.com/flatpak/flatpak-builder-tools).

---

## Verifying a package

After installing any of the above:

- `orbitdeck` launches from a terminal, and **OrbitDeck** appears in the desktop
  menu (Science / Education / Ham Radio).
- The window icon and the software-center entry render (icon + metainfo).
- First run works **offline** with the bundled catalog; **Update GP** fetches
  live elements.

## Keeping versions in sync

Every helper carries the version string. On a release, bump:

- `orbitdeck/__init__.py`, `pyproject.toml`, `orbitdeck.spec`
- `packaging/PKGBUILD` (`pkgver`)
- `packaging/orbitdeck.spec.rpm` (`Version`)
- `packaging/debian/changelog` (new entry)

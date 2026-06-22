# Building standalone OrbitDeck executables

OrbitDeck is packaged with [PyInstaller](https://pyinstaller.org/). The result
is a self-contained app that bundles the Python interpreter, OrbitDeck, and all
dependencies (numpy, matplotlib, tkinter) so users **don't need Python
installed**.

> **PyInstaller does not cross-compile.** A Windows `.exe` must be built on
> Windows, a macOS `.app` on macOS, and a Linux binary on Linux. To produce all
> targets, use the GitHub Actions workflow in `.github/workflows/build.yml`,
> which builds on a runner matrix.

### Automated build targets

The `build.yml` workflow produces one artifact per target:

| Target | Runner | Artifact |
| --- | --- | --- |
| Windows x86_64 | `windows-latest` | `OrbitDeck-windows` |
| macOS Apple Silicon | `macos-latest` (arm64) | `OrbitDeck-macos-arm64` |
| macOS Intel | `macos-13` (x86_64) | `OrbitDeck-macos-intel` |
| Linux x86_64 | `ubuntu-latest` | `OrbitDeck-linux-x86_64` |
| Raspberry Pi OS 64-bit | `ubuntu-22.04-arm` (arm64) | `OrbitDeck-raspberrypi-arm64` |

**Raspberry Pi build.** The Pi target builds natively on GitHub's arm64 Linux
runner. Two things make it work: `ubuntu-22.04-arm` ships glibc 2.35, which is
*older* than Raspberry Pi OS Bookworm's glibc 2.36, so the binary loads on a
current 64-bit Pi (a binary built on the newer `ubuntu-24.04-arm` would fail with
a `GLIBC_2.3x not found` error); and because cartopy has no aarch64 PyPI wheel,
the job installs GEOS/PROJ via `apt` and builds cartopy from source (falling back
to OrbitDeck's bundled coastlines if that build fails). The artifact targets
**64-bit (aarch64) Raspberry Pi OS only** — it will not run on the legacy 32-bit
(armhf) Pi OS.

> ⚠️ **arm64 runners require a public repository.** GitHub's free `*-arm` hosted
> runners only work in **public** repos; in a private repo the Raspberry Pi job
> will fail to start. For a private repo, either make the build workflow run in a
> public fork, attach a **self-hosted arm64 runner** (e.g. an actual Raspberry Pi
> registered as a runner) and change `runs-on` to its label, or use a paid arm64
> **larger runner**.

## Quick start (current platform)

```bash
# from the repo root, ideally in a clean virtual environment
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -e ".[full]"             # OrbitDeck + ALL optional dependencies
pip install pyinstaller
pyinstaller orbitdeck.spec
```

> **Always build with `[full]`.** A standalone bundle should include every
> optional dependency (`sgp4`, `cartopy`, `openpyxl`) so the shipped app has the
> C-accelerated propagator, high-resolution coastlines, and native `.xlsx`
> export baked in — end users of a frozen build can't add extras themselves.

The bundle appears in `dist/OrbitDeck/` (a one-folder app). Launch it with:

- **Windows:** `dist\OrbitDeck\OrbitDeck.exe`
- **macOS:** `dist/OrbitDeck.app` (double-click, or `open dist/OrbitDeck.app`)
- **Linux:** `dist/OrbitDeck/OrbitDeck`

A helper script is provided:

```bash
python packaging/build.py        # cleans, runs PyInstaller, prints the output path
```

## One-file vs one-folder

The spec produces a **one-folder** bundle (faster startup, easy to inspect). For
a single distributable file, the simplest approach is to zip `dist/OrbitDeck/`.
A true one-file `.exe` is possible but starts slower (it unpacks to a temp dir on
each launch) and trips some antivirus heuristics; one-folder is recommended for a
matplotlib/tkinter app.

## Icons

- **Windows** uses `orbitdeck/gui/assets/icon.ico` (already in the repo).
- **Linux** uses `orbitdeck/gui/assets/icon-256.png` at runtime for the window.
- **macOS** needs an `.icns`, which must be generated on a Mac:

  ```bash
  # from orbitdeck/gui/assets/, with icon-512.png present
  mkdir icon.iconset
  for s in 16 32 64 128 256 512; do
    sips -z $s $s icon-512.png --out icon.iconset/icon_${s}x${s}.png
    d=$((s*2)); sips -z $d $d icon-512.png --out icon.iconset/icon_${s}x${s}@2x.png
  done
  iconutil -c icns icon.iconset -o icon.icns
  ```

  Place `icon.icns` next to the other icons; the spec picks it up automatically.

> **Windows taskbar icon.** The `.exe` icon (from `icon.ico`, set by the spec)
> and the *taskbar* icon are governed separately. OrbitDeck sets an explicit
> **AppUserModelID** (`OrbitDeck.SatelliteTracker`) at startup and applies the
> bundled icon to the window, so the taskbar shows OrbitDeck's own icon and
> groups its windows under OrbitDeck rather than the generic Python host icon.
> This is handled in the app — no build step needed — but if you fork the
> launcher, keep the `SetCurrentProcessExplicitAppUserModelID` call *before* the
> Tk window is created, or Windows reverts to the host icon. If a stale icon
> persists after an upgrade, it's usually the Windows icon cache; signing/renaming
> the exe or clearing the cache resolves it.

## Common gotchas (already handled in the spec)

- **matplotlib data files** (fonts, `mpl-data`) and **its native extensions** are
  collected via `collect_all("matplotlib")`, and on Windows the spec also copies
  matplotlib's vendored DLL directory (`matplotlib.libs`, where delvewheel puts
  FreeType etc.). Without that DLL directory a Windows build imports but then
  crashes at launch with **`ImportError: DLL load failed while importing
  ft2font`** — because `ft2font.pyd` ships but its FreeType DLL is missing from
  the bundle. The spec does the same for `numpy` and `PIL`. (You may see this as
  a confusing *double* traceback in older builds: the real `ft2font` error,
  followed by `'NoneType' object has no attribute 'write'` — that second one is
  just the windowed app having no `sys.stderr` to print the first to; `run.py`
  now reports startup failures via a Tk dialog instead.)
- **tkinter / Tcl-Tk** runtimes are bundled automatically; the hidden imports in
  the spec make the Tk backend resolve.
- **HTTPS / SSL certificates.** Frozen builds — **especially on macOS** — can
  fail network fetches (AMSAT GP, SatNOGS transponders, NOAA space weather) with
  `CERTIFICATE_VERIFY_FAILED`, because Python's default CA certificate path isn't
  present in the bundle. OrbitDeck handles this three ways: `certifi` is a
  dependency, its CA bundle is collected into the build (`collect_data_files
  ("certifi")`), and the app sets `SSL_CERT_FILE` to that bundle at startup. No
  user action is needed. (If you ever see this error from a source checkout
  rather than a bundle, run `pip install certifi` or, on macOS with a python.org
  build, the bundled **Install Certificates.command**.)
- **`~/.orbitdeck`** (config, GP cache, transponder cache, space-wx cache) is
  created in the user's home directory at runtime, so it works the same whether
  run from source or from a frozen bundle.
- The app **runs offline**: live data (GP, transponders, space weather) is
  fetched on demand and cached; without a network the app uses bundled sample
  elements and the last cached data.

## Reducing size

The spec already excludes Qt, wx, pytest, and IPython. **UPX compression is
disabled** on purpose: it can corrupt compressed native DLLs (numpy, the
FreeType library behind matplotlib's `ft2font`, and PROJ behind cartopy),
producing runtime "DLL load failed" crashes — exactly the kind of failure that
is hard to diagnose in a frozen GUI app. Typical bundle size is ~150–250 MB
(matplotlib + numpy dominate); if you want it smaller, prefer trimming
`excludes` over re-enabling UPX.

## Code signing & notarization

Unsigned apps trigger **SmartScreen** (Windows) and **Gatekeeper** (macOS)
warnings — on macOS an unsigned/un-notarized app is blocked outright for most
users. Signing is optional for a local build but effectively required for
distribution. Both platforms need a **paid identity** (details below), so budget
for that before you start.

> Quick reality check on costs and lead time: an Apple Developer Program
> membership is **US$99/year** and enrolment can take a day or two. Windows
> signing is either a **~US$10/month** Microsoft cloud service or a **~US$200–600/year**
> certificate from a commercial CA; identity validation can take anywhere from
> minutes to several days. Plan ahead.

---

### Windows

Windows verifies executables with **Authenticode**. Microsoft **SmartScreen**
then decides whether to warn the user; signing establishes the publisher
identity that SmartScreen reputation accrues to. As of 2024 Microsoft treats OV
and EV the same for SmartScreen, and reputation builds over time from clean
download volume either way — there is no longer an "instant green" certificate.

Since **June 2023** the private key for any publicly trusted code-signing
certificate must live in **hardware** (a FIPS USB token) or a **cloud HSM** — you
can no longer get a plain downloadable `.pfx`. That makes the cloud services the
simplest path.

**Option A — Microsoft Artifact Signing (formerly Trusted Signing) — recommended**

A cloud signing service: Microsoft holds the key, issues short-lived
certificates per-signature, and there is no token to manage. It reached General
Availability in 2026 but **Public Trust certificates are limited by region** —
currently organizations in the US, Canada, EU, and UK, and **individual
developers in the US and Canada only**. Check current eligibility before relying
on it.

1. Have (or create) an **Azure account** with a pay-as-you-go subscription.
   Pricing starts around **US$9.99/month**.
2. In the Azure portal, register the **Microsoft.CodeSigning** resource provider
   and create an **Artifact Signing account** (pick a region above).
3. Open **Identity validations** → choose **Individual** or **Organization** →
   **Public**. Individual validation uses Microsoft Entra Verified ID: you submit
   a government photo ID and a selfie/biometric check; details must match your
   Azure billing account exactly. Approval is often minutes to a few hours, up to
   a few days.
4. Create a **certificate profile** (this is the template Azure uses to mint each
   short-lived cert).
5. Assign yourself the **Trusted Signing Certificate Profile Signer** role on the
   account (Access control / IAM).
6. Install the **Trusted Signing dlib** + the Windows SDK's `signtool`, and sign
   with a metadata file pointing at your endpoint/account/profile:

   ```powershell
   signtool sign /v /debug /fd SHA256 /tr "http://timestamp.acs.microsoft.com" ^
     /td SHA256 /dlib "C:\path\Azure.CodeSigning.Dlib.dll" ^
     /dmdf "C:\path\metadata.json" "dist\OrbitDeck\OrbitDeck.exe"
   ```

   where `metadata.json` contains your `CodeSigningAccountName`,
   `CertificateProfileName`, and the account endpoint URL. This integrates
   cleanly with GitHub Actions / Azure DevOps — no physical token on the build
   machine.

**Option B — A commercial OV (or EV) certificate**

Buy from a CA such as SSL.com, DigiCert, Sectigo, or GlobalSign.

1. Choose **OV** (Organization Validation; your company name appears as
   publisher) or, as a solo dev, an **IV / sole-proprietor** certificate. **EV**
   costs more and is only strictly required for kernel-mode drivers — not needed
   for a normal app.
2. The CA validates you (business registration for OV, or government ID for an
   individual). Expect **1–5 business days**; expedited options exist.
3. The CA ships an **encrypted USB token** (e.g. a YubiKey FIPS) with the key, or
   enrols you in their **cloud HSM** (e.g. SSL.com eSigner). The key is never a
   downloadable file.
4. Sign with `signtool` (Windows SDK). With a USB token plugged in:

   ```powershell
   signtool sign /fd SHA256 /a /tr "http://timestamp.sectigo.com" /td SHA256 ^
     "dist\OrbitDeck\OrbitDeck.exe"
   signtool verify /pa /v "dist\OrbitDeck\OrbitDeck.exe"
   ```

   The token prompts for a PIN per signature (a known annoyance for CI — the
   cloud options above avoid it). **Always timestamp** (`/tr` + `/td`) so the
   signature stays valid after the certificate expires.

> Note: under a 2026 CA/Browser Forum rule, individual issued certificates are
> now capped at ~458 days even within a multi-year purchase, so you may reissue
> from the token/cloud more often. Your purchased term is unaffected.

PyInstaller doesn't sign on Windows; sign the produced `OrbitDeck.exe` (and your
installer, if you build one) as a **post-build step**.

---

### macOS

macOS apps need to be **signed with a Developer ID Application** certificate
**and notarized** by Apple, then have the notarization ticket **stapled**.
Without this, Gatekeeper blocks the app for anyone who didn't build it.

**1. Enrol in the Apple Developer Program (US$99/year).**

- Go to <https://developer.apple.com/programs/> and enrol with your Apple ID
  (enable two-factor auth first). You can join as an **Individual / Sole
  Proprietor** or as an **Organization** (the latter needs a D-U-N-S number and
  shows your company name as the developer).
- Apple verifies you; enrolment typically completes within a day or two. A newly
  enrolled team can briefly report *"Team is not yet configured for
  notarization"* — wait a few hours and retry if so.

**2. Create the signing certificate.**

- In Xcode: **Settings → Accounts → (your team) → Manage Certificates → ＋ →
  Developer ID Application**. (Or create it on the Apple Developer website under
  *Certificates*.) This installs a `Developer ID Application: Your Name (TEAMID)`
  identity into your login keychain.
- Confirm it's present:

  ```bash
  security find-identity -p codesigning -v
  ```

**3. Sign the app with the hardened runtime.**

The hardened runtime (`--options runtime`) is **required** for notarization:

```bash
codesign --deep --force --options runtime --timestamp \
  --sign "Developer ID Application: Your Name (TEAMID)" \
  dist/OrbitDeck.app

codesign --verify --strict --verbose=2 dist/OrbitDeck.app
```

You can also have PyInstaller sign during the build by setting
`codesign_identity="Developer ID Application: Your Name (TEAMID)"` (and an
`entitlements_file` if needed) in `orbitdeck.spec` — but a separate `codesign`
pass after the build is easier to debug. A pure-Python + Tk app usually needs no
special entitlements.

**4. Store notarization credentials once.**

Create an **app-specific password** for your Apple ID at
<https://appleid.apple.com> (Sign-In & Security → App-Specific Passwords), then
save a reusable keychain profile:

```bash
xcrun notarytool store-credentials "OrbitDeckNotary" \
  --apple-id "you@example.com" \
  --team-id "TEAMID" \
  --password "abcd-efgh-ijkl-mnop"      # the app-specific password
```

(For CI, an **App Store Connect API key** works in place of the Apple ID.)

**5. Notarize, then staple.**

Notarization scans a **zip, DMG, or pkg** — not a bare `.app`. Zip it, submit,
and on success staple the ticket so the app validates offline:

```bash
ditto -c -k --keepParent dist/OrbitDeck.app dist/OrbitDeck.zip

xcrun notarytool submit dist/OrbitDeck.zip \
  --keychain-profile "OrbitDeckNotary" --wait        # waits for Accepted/Invalid

xcrun stapler staple dist/OrbitDeck.app              # staple the .app itself
xcrun stapler validate dist/OrbitDeck.app
```

If a submission is rejected, read the log to find the offending binary:

```bash
xcrun notarytool log <submission-id> --keychain-profile "OrbitDeckNotary"
```

Distribute the **stapled** `.app` (ideally inside a signed, stapled DMG). Verify
the end-user experience with:

```bash
spctl --assess --type execute --verbose=4 dist/OrbitDeck.app   # should say: accepted
```

---

### Spec hooks

`orbitdeck.spec` already exposes `codesign_identity` and `entitlements_file` on
the macOS build for the optional in-build signing described above; they default
to `None` (unsigned). Leave them `None` and sign as a post-build step if you
prefer the explicit `codesign` / `notarytool` flow, which is easier to automate
and diagnose.

---

## Professional installers

The PyInstaller output above is a **folder** (or `.app`) you'd have to zip. For
a polished end-user experience, wrap it in a real installer: a Windows
**Setup.exe / MSI** that installs to *Program Files*, adds Start-menu and
optional desktop shortcuts, and registers an uninstaller; and a macOS **DMG**
(drag-to-Applications) or **`.pkg`** installer.

Build the standalone bundle first (`pyinstaller orbitdeck.spec`), then feed it to
one of the tools below. **Sign and notarize the finished installer too**, not
just the inner app — see [Code signing & notarization](#code-signing--notarization).

### Windows — Inno Setup (recommended)

[Inno Setup](https://jrsoftware.org/isinfo.php) is free, scriptable, and
produces a single `OrbitDeck-Setup.exe`. Install it, then create
`packaging/windows/orbitdeck.iss`:

```ini
#define MyAppName "OrbitDeck"
#define MyAppVersion "0.35.6"
#define MyAppPublisher "Paul Stoetzer, N8HM"
#define MyAppURL "https://github.com/prstoetzer/OrbitDeck"
#define MyAppExeName "OrbitDeck.exe"

[Setup]
AppId={{B7E6C2A0-0000-4000-A000-ORBITDECK0001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=dist
OutputBaseFilename=OrbitDeck-{#MyAppVersion}-Setup
; LicenseFile=..\..\LICENSE

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
; the entire one-folder PyInstaller bundle
Source: "..\..\dist\OrbitDeck\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
```

Compile from the repo root after building the bundle:

```powershell
pyinstaller orbitdeck.spec
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging\windows\orbitdeck.iss
# -> dist\OrbitDeck-0.35.6-Setup.exe
```

Then **sign the installer** with `signtool` exactly as for the `.exe`. Inno
Setup gives a familiar wizard, an entry in *Apps & features*, and a clean
uninstall.

> **MSI alternative.** If your environment requires a true `.msi` (group-policy
> deployment, enterprise software management), use
> [WiX Toolset](https://wixtoolset.org/) instead — it's more verbose but emits a
> standard MSI. For most users Inno Setup's `Setup.exe` is simpler and equally
> professional.

### macOS — a drag-install DMG (recommended)

The familiar macOS experience is a disk image showing your `.app` beside an
*Applications* shortcut. [`create-dmg`](https://github.com/create-dmg/create-dmg)
automates a styled image:

```bash
brew install create-dmg

# build + sign + notarize the .app first (see Code signing & notarization), then:
create-dmg \
  --volname "OrbitDeck" \
  --volicon "orbitdeck/gui/assets/icon.icns" \
  --window-size 540 380 \
  --icon-size 110 \
  --icon "OrbitDeck.app" 150 190 \
  --app-drop-link 390 190 \
  --hdiutil-quiet \
  "dist/OrbitDeck-0.35.6.dmg" \
  "dist/OrbitDeck.app"
```

Then **sign and notarize the DMG itself** so it opens without a Gatekeeper
prompt:

```bash
codesign --force --sign "Developer ID Application: Your Name (TEAMID)" \
  "dist/OrbitDeck-0.35.6.dmg"
xcrun notarytool submit "dist/OrbitDeck-0.35.6.dmg" \
  --keychain-profile "OrbitDeckNotary" --wait
xcrun stapler staple "dist/OrbitDeck-0.35.6.dmg"
```

> **`.pkg` alternative.** For an installer that places the app and can run
> pre/post-install scripts (or for managed/MDM deployment), build a component
> package and wrap it for distribution:
> ```bash
> pkgbuild --root dist/OrbitDeck.app \
>   --install-location "/Applications/OrbitDeck.app" \
>   --identifier io.github.prstoetzer.OrbitDeck \
>   --version 0.35.6 OrbitDeck-component.pkg
> productbuild --sign "Developer ID Installer: Your Name (TEAMID)" \
>   --package OrbitDeck-component.pkg "dist/OrbitDeck-0.35.6.pkg"
> ```
> Note a `.pkg` is signed with a **Developer ID *Installer*** certificate
> (distinct from the *Application* certificate used for the app), then notarized
> and stapled the same way. A drag-install DMG is the more common choice for a
> single GUI app.

### Where this fits in CI

A full release pipeline per OS is: build the bundle → sign the inner app/exe →
build the installer → sign **and** notarize the installer → publish. PyInstaller,
Inno Setup, and `create-dmg` are all command-line driven, so this slots into
GitHub Actions runners (`windows-latest`, `macos-latest`) end to end.

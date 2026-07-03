# TASHIL: Smart Health Management System
## Documentation de traçabilité — v1.1.35

**Copyright :** ILINE TECH 2026 BY FERAK ALADDIN
**Dépôt :** https://github.com/Aladdinweb/TASHIL-ES
**Date :** 2026-07-02

---

## But de ce fichier

Coller ce fichier au début d'une nouvelle conversation Claude
pour restaurer instantanément le contexte complet du projet,
sans réexpliquer l'architecture ni l'historique.
Mettre à jour après chaque push de version.

---

## 1. Vue d'ensemble

- **Nom :** TASHIL — Smart Health Management System
- **Type :** Application Windows desktop (PyInstaller)
- **Stack :** Python 3.11 + CustomTkinter + SQLite
- **CI/CD :** GitHub Actions → Release automatique
- **Repo :** Aladdinweb/TASHIL-ES (branch: main)
- **EXE :** EPSP_CongeManager.exe
- **Version :** v1.1.35 (patch auto-incrémenté par CI)

---

## 2. Architecture des fichiers

```
TASHIL-ES/
├── main.py                    # Entrée, splash, SmartHub
├── STATE.md                   # Ce fichier
├── epsp_conge.spec            # PyInstaller config
├── app/
│   ├── config.py              # Branding, 20 services, grades
│   ├── utils/
│   │   ├── database.py        # SQLite + backup auto
│   │   ├── version.py         # v1.1.0 ancre, patch CI
│   │   ├── migration.py       # Migrations + colonne service
│   │   ├── services.py        # Import depuis config.py
│   │   ├── deduction_engine.py # FIFO + rollover 1er Mai
│   │   ├── employes_dao.py    # CRUD employes
│   │   ├── conges_dao.py      # CRUD conges
│   │   ├── polycliniques_dao.py # CRUD polycliniques
│   │   ├── theme.py           # Palette COULEURS/POLICES
│   │   └── updater.py         # MAJ auto (DL dans TEMP)
│   └── views/
│       ├── app_principale.py  # Navigation 7 onglets
│       ├── vue_dashboard.py   # Dashboard thread-safe
│       ├── vue_employes.py    # Gestion employes
│       ├── vue_conge.py       # Onglet Conges
│       ├── vue_reliquat.py    # Reliquats FIFO
│       ├── vue_bordereau.py   # Bordereau + FIFO
│       ├── vue_tableau_service.py # Grille roster
│       ├── vue_administration.py  # Messagerie
│       ├── vue_activation.py  # Premiere config
│       ├── dialogue_employe.py
│       ├── dialogue_conge_rapide.py
│       ├── dialogue_annulation.py
│       ├── dialogue_transfert.py
│       └── fiche_employe.py
└── .github/workflows/
    └── build_windows.yml      # CI/CD PyInstaller
```

---

## 3. Regles architecturales IMMUABLES

### Regle 1 — CustomTkinter place()
- width/height TOUJOURS dans le constructeur du widget
- place() utilise uniquement x/y/relwidth/relheight
- Violation = ValueError silencieux sous PyInstaller

### Regle 2 — Frames racines des vues
- SEUL moyen valide : vue.place(x=0, y=0, relwidth=1, relheight=1)
- INTERDIT : vue.pack(fill="both", expand=True) = ecran noir

### Regle 3 — Sidebar
- CTkScrollableFrame + pack() en interne
- Badge = emoji uniquement, jamais texte "dz"

### Regle 4 — Initialisation DB
- initialize_database() + migrer() AVANT ctk.CTk()

### Regle 5 — Refresh interception
- _modal_actif() verifie CTkToplevel avant refresh
- Jamais fermer un formulaire actif

### Regle 6 — FIFO (logique gelee)
- CONGE_ANNUEL = deduction reliquat le plus ancien
- MALADIE/MATERNITE = sans deduction
- Rollover 1er Mai = executer_rollover_mai()

### Regle 7 — Updater
- Telechargement TOUJOURS dans %TEMP%
- Jamais dans le dossier exe (Desktop bloque)

### Regle 8 — Crash dump
- Erreur boot = tashil_boot_error.txt avant sys.exit

---

## 4. Signature du code (Windows)

Generer un certificat auto-signe (PowerShell) :

```powershell
$cert = New-SelfSignedCertificate `
  -Subject "CN=TASHIL ILINE TECH 2026" `
  -CertStoreLocation "Cert:\CurrentUser\My" `
  -KeyExportPolicy Exportable -KeySpec Signature

$pwd = ConvertTo-SecureString "TASHIL2026!" -AsPlainText -Force
Export-PfxCertificate -Cert $cert -FilePath "tashil_cert.pfx" -Password $pwd

[Convert]::ToBase64String([IO.File]::ReadAllBytes("tashil_cert.pfx")) |
  Out-File "tashil_cert_b64.txt"
```

Ajouter dans GitHub Secrets :
- SIGNING_CERT_B64 = contenu de tashil_cert_b64.txt
- SIGNING_CERT_PASSWORD = TASHIL2026!

---

## 5. Etat des modules

| Module           | Etat | Description                          |
|------------------|------|--------------------------------------|
| Dashboard        | OK   | 4 tuiles, annuaire, LA REPRISE       |
| Employes         | OK   | 4 champs obligatoires                |
| Conges           | OK   | Menu clic droit, FIFO                |
| Reliquats        | OK   | Matricule masque, colonnes vides     |
| Bordereau        | OK   | Scan FIFO, export Excel              |
| Tableau Service  | OK   | Grille editable, mois FR             |
| Administration   | OK   | Messagerie inter-polycliniques       |
| Smart Hub        | OK   | Socket port 7890 daemon              |
| MAJ automatique  | OK   | DL TEMP, bat remplacement            |

---

## 6. Services cliniques (20)

Urgences, Consultation, Dentaire, PMI, Pediatre,
Psychologue, Vaccin, Sage Femme, Salle de Soin, ECG,
Pharmacie, Medecine Interne/Endocrinologue,
Service Ophtalmologie, Secretariat, Dentaire Urgences,
Dermatologue, Pneumologue, ORL, Administration, Autre

---

## 7. Polycliniques EPSP ES-SENIA (7)

| Code    | Nom                                        |
|---------|--------------------------------------------|
| POLY_01 | POLYCLINIQUE ES SENIA                      |
| POLY_02 | POLYCLINIQUE AADL AIN BEIDA MABROUK LOUCIF |
| POLY_03 | POLYCLINIQUE AIN BEIDA 1                   |
| POLY_04 | POLYCLINIQUE AIN BEIDA 2                   |
| POLY_05 | POLYCLINIQUE SIDI MAAROUF                  |
| POLY_06 | POLYCLINIQUE SIDI CHAHMI                   |
| POLY_07 | POLYCLINIQUE EL KERMA                      |

---

## 8. Historique corrections

| Version  | Correction                                  |
|----------|---------------------------------------------|
| v1.1.21  | Fix ecran noir — DB avant tkinter           |
| v1.1.28  | Fix ValueError — place() constructeur       |
| v1.1.32  | Sidebar scrollable, modules rendus          |
| v1.1.33  | Mois FR, badge drapeau, tuiles              |
| v1.1.34  | Migration vers TASHIL-ES                    |
| v1.1.35  | Fix Errno 13 updater TEMP, STATE.md complet |

---

## 2. Build & Release Pipeline

- **Build:** GitHub Actions (`.github/workflows/build.yml`) — `assembleRelease`, no local Android Studio.
- **Signing:** Production keystore `~/thieves_trap_release.jks` (JKS format — **critical**: PKCS12 from Java 17 default breaks Android's signer with "Tag number over 30"). Stored as base64 in GitHub Secret `KEYSTORE_BASE64`, with `KEYSTORE_PASSWORD`, `KEY_ALIAS`, `KEY_PASSWORD` also as secrets.
- **APK naming:** `build.gradle`'s `outputFileName` block auto-names output as `Thieves_Trap_v${versionName}_Final.apk`.
- **Artifact discovery in build.yml:** dynamic (`find app/build/outputs/apk/release -name "*.apk"`) — never hardcode the filename/version in build.yml again, it broke multiple times.
- **OTA delivery mechanism:** GitHub **Releases** (not Actions artifacts!). `UpdateManager.kt` hits `api.github.com/repos/Aladdinweb/ThievesTrap/releases/latest`. Actions artifacts are NOT visible to this endpoint — every version bump requires manually publishing a Release with the signed APK attached as an asset.
- **Release publishing tool:** `release_tool/create_release.sh <version> <apk_path>` — automates Release creation + asset upload via GitHub API from Termux.
- **IMPORTANT CAVEAT discovered:** Once a device has a build installed signed with the *old debug keystore*, OTA updates signed with the *new release keystore* will fail to install ("problem parsing the package" = signature mismatch, not corruption). Must uninstall once and side-load manually to switch keystores; all subsequent OTA updates work fine since the keystore is now consistent.

### Standard release workflow (every version bump):
```bash
# 1. Push code changes (via the relevant push_vX.sh script)
bash push_vXXX.sh

# 2. Wait for GitHub Actions to go green (~3-5 min)
# 3. Download artifact zip from github.com/Aladdinweb/ThievesTrap/actions
cd /sdcard/Download
unzip -o Thieves_Trap_vX.X.X_Final.apk.zip
ls -lh Thieves_Trap_vX.X.X_Final.apk   # must be several MB, not KB

# 4. Delete old GitHub Release of same version if re-publishing
# (github.com/Aladdinweb/ThievesTrap/releases -> delete release + tag)

# 5. Publish release
cd /sdcard/Download/release_tool
bash create_release.sh X.X.X /sdcard/Download/Thieves_Trap_vX.X.X_Final.apk

# 6. Test in-app: sidebar -> Check for Update
```

---

## 3. File Map — What Each File Does

### Kotlin source (`app/src/main/java/com/thievestrap/`)

| File | Purpose |
|---|---|
| `MainActivity.kt` | Main screen: ARM/DISARM button, shield status UI, nav drawer (Settings, Premium, PIN change, Survival Timer, Watch Tether, Check for Update, Language). First-ARM guidance dialog (`isFirstArm` pref). Watch Tether ℹ️ badge wired to info dialog. |
| `MonitorService.kt` | Core foreground service. Handles SMS commands (`SMS_COMMAND` action from static receiver), SIM swap trap state machine, silent-mode grace period, theft mode toggles, location updates, all SMS template building (`buildFullInfo`, IMEI injection, PING_NOTE footer). Uses `serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)` so SMS processing and SIM-trap timer never block each other. |
| `SmsCommandReceiver.kt` | **Static**, manifest-registered (`priority=999`, `exported=true`) SMS receiver — survives process death, unlike a dynamic receiver. Forwards `SMS_RECEIVED` to `MonitorService` via explicit intent + `startForegroundService`. Has `@Volatile lastProcessedTime` dedup filter (5s window) to prevent double-processing. **This is now the SOLE SMS entry point** — `MonitorService`'s old dynamic `smsReceiver` was removed in v2.7.9b to fix duplicate SMS replies. |
| `SmartwatchMonitorService.kt` | Bluetooth ACL connection monitor for paired smartwatch ("Watch Tether" feature). On disconnect: vibrate + `DevicePolicyManager.lockNow()` + 5-min countdown notification with **🚨 TRIGGER ALARM** / **🔕 DISARM/MUTE** / **I'm Safe** (no PIN) actions. On expiry: one emergency SMS with GPS. Auto-aborts on reconnect. |
| `RemoteGuideActivity.kt` | "Remote Control Guide" screen — lists all SMS commands using `item_command.xml` rows. Each row's real IDs are `tv_cmd_text` / `tv_cmd_desc` / `btn_copy_cmd` (NOT `tv_command_name`/`tv_command_desc` — that was a v2.7.9b bug, fixed in v2.8.0). Has ℹ️ badge (`btn_plan_b_info`) explaining the Plan B dynamic-PIN mechanism. |
| `UpdateManager.kt` | OTA update logic. `checkForUpdate()` → GitHub Releases API → compares `tag_name` (strips "v") against `BuildConfig.VERSION_NAME` → shows AlertDialog if newer → `DownloadManager` streams APK to `Downloads/` → `FileProvider` + `ACTION_VIEW` launches installer. Validates downloaded file size (`MIN_APK_BYTES = 1MB`) to catch corrupt/wrapper downloads before attempting install. |
| `SettingsActivity.kt` | Settings screen (IMEI, emergency contacts, Telegram bot setup, theft alert toggles, SMS test). Airplane Mode row fully removed (v2.7.6). |
| `SelfieService.kt` / `SelfiesActivity.kt` | Intruder selfie capture (Device Admin triggered, on failed unlock) + gallery viewer. |
| `SurvivalTimerService.kt` | "I'm still safe" dead-man's-switch timer — sends emergency SMS if not cancelled in time. |
| `SafeConfirmReceiver.kt` / `SafeConfirmActivity.kt` | "I'm Safe" button handling — stops `SurvivalTimerService` directly via `PendingIntent.getService`, **no PIN required**. |
| `AlarmService.kt` | Max-volume siren service, controlled via `START_ALARM`/`STOP_ALARM` actions — used by remote ALARM command, Watch Tether TRIGGER ALARM, and Plan B ALARM. |
| `LicenseManager.kt` | Free/Premium gating logic. |
| `TelegramUploader.kt` | Sends messages/photos to Telegram bot (@ThievesTrap_Alert_bot) — premium feature. |
| `BootReceiver.kt` | Restarts monitoring on device boot if `running=true`. |
| `DeviceAdminReceiver.kt` | Device Admin callbacks — failed/succeeded password attempts trigger selfie + alert. |
| `LocaleHelper.kt` / `Strings.kt` | EN/FR/AR localization. |

### Layouts (`app/src/main/res/layout/`)

| File | Notes |
|---|---|
| `activity_main.xml` | Main screen + right nav drawer (`DrawerLayout`, `gravity="end"`). Drawer order: Settings → Premium → Fingerprint/Change PIN → **PERSONAL SAFETY** section (Survival Timer with ℹ️ badge `nav_survival_info` → Watch Tether with ℹ️ badge `nav_watch_tether_info`, added v2.8.0, matches Survival Timer pattern exactly → Check for Update `nav_check_update`, crimson `#FF1A1A`) → spacer → Language at very bottom. |
| `activity_settings.xml` | DEVICE STATUS ALERTS section — Airplane Mode row permanently deleted. |
| `activity_remote_guide.xml` | Header has `btn_plan_b_info` ℹ️ badge next to title. Body is a list of `<include layout="@layout/item_command">` rows with unique `android:id`s (`cmd_where`, `cmd_history`, `cmd_info`, `cmd_status`, `cmd_battery`, `cmd_imei`, `cmd_sim`, `cmd_alarm`, `cmd_stop_alarm`, `cmd_lock`, `cmd_selfie`, `cmd_ping2`, `cmd_ping5`, `cmd_stop_ping`, `cmd_active`, `cmd_deactivate`, `cmd_disarm`). |
| `item_command.xml` | **Real IDs**: `tv_cmd_text` (command keyword, bold monospace), `tv_cmd_desc` (description), `btn_copy_cmd` (copy-to-clipboard button). Default placeholder text is "WHERE" / "Get current GPS location" — MUST be overwritten programmatically per-row in `RemoteGuideActivity.setupCommandRows()`, or every row shows "WHERE" (this was a real bug, fixed v2.8.0). |
| `file_paths.xml` | FileProvider paths — `pictures`, `external_pictures`, `external_dcim`, plus `downloads` (`Download/`, added v2.7.9 for OTA APK install). |

### Manifest & Build

| File | Key points |
|---|---|
| `AndroidManifest.xml` | `SmsCommandReceiver` static receiver, `priority="999"`, `permission="android.permission.BROADCAST_SMS"`. `REQUEST_INSTALL_PACKAGES` permission (OTA). Bluetooth permissions (Watch Tether). FileProvider authority `${applicationId}.fileprovider` shared by selfies + OTA APK install. No airplane-mode anything anywhere. |
| `app/build.gradle` | `versionCode 124`, `versionName "2.8.0"`. `outputFileName` block names APK by version. Release `minifyEnabled true`. |
| `.github/workflows/build.yml` | `assembleRelease` with signing params passed via `-Pandroid.injected.signing.*` flags reading from GitHub Secrets. Dynamic APK discovery (no hardcoded filename). |

---

## 4. SMS Remote Command Reference (current, v2.8.0)

**Free (no premium, no registration check):**
- `WHERE` / `LOCATION` / `LOC` / `FIND` — GPS + Maps link, exactly ONE SMS reply, includes IMEI + PING_NOTE footer.
- `HELP`, `STATUS` (basic)

**Premium (requires registered sender OR Plan B PIN):**
- `INFO`/`DEVICE`, `BATTERY`/`BAT`, `SIM`, `IMEI`, `HISTORY`
- `ALARM`/`RING`, `STOP ALARM`/`SILENCE`, `LOCK`, `SELFIE`/`PHOTO`/`PICTURE`
- `PING <mins>`, `STOP PING`
- `ACTIVE`/`ACTIVATE`, `DEACTIVATE`, `DISARM <pin>`

**Plan B (dynamic PIN, works from ANY unknown phone number):**
- Pattern: `COMMAND PIN` e.g. `WHERE 2026`, `ALARM 2026`
- PIN = live value of `password` in SharedPreferences (the security PIN)
- Bypasses registration entirely — replies directly to the unknown sender
- Implemented in `MonitorService.matchPlanBCommand()` + `handlePlanBCommand()`

**Loop guards (all in `MonitorService.processSmsPdus()`):**
1. Ignore sender if it matches own SIM number
2. Multi-part PDU concatenation per sender before parsing
3. Per-sender 5-second cooldown (`last_cmd_<digits>` pref)

---

## 5. Smart SIM Trap (lightweight, v2.7.8+)

1. SIM change/removal detected → `SIM_CHANGED_PENDING_ALERT=true` in prefs.
2. Register `ConnectivityManager.NetworkCallback` for `TRANSPORT_CELLULAR`, **`onAvailable()` only** — do NOT wait for `NET_CAPABILITY_VALIDATED` (caused freezes in v2.7.7, fixed in v2.7.8).
3. On signal: non-blocking 10s coroutine `delay()` (GPS warm-up), then send ONE emergency SMS via `SmsManager.getDefault()` with new carrier/line/IMEI/location.
4. Clear `SIM_CHANGED_PENDING_ALERT` — one-shot, survives process restart (re-registers listener in `onCreate()` if flag still true).

---

## 6. Watch Tether Mechanism (v2.7.6+, UX polished v2.7.9b/v2.8.0)

1. User pairs Bluetooth smartwatch, enables switch in sidebar (requires BT on + a bonded device).
2. `SmartwatchMonitorService` monitors `ACTION_ACL_DISCONNECTED`/`ACTION_ACL_CONNECTED`.
3. On disconnect: vibration pattern + `lockNow()` + notification with 3 actions: **I'm Safe** (no PIN), **🚨 TRIGGER ALARM**, **🔕 DISARM/MUTE**.
4. 5-minute countdown; reconnect auto-cancels.
5. On expiry: one emergency SMS with location to Emergency Contact.
6. Sidebar ℹ️ badge (`nav_watch_tether_info`) → explains full mechanism in AlertDialog.

---

## 7. Known Issues / Gotchas (don't repeat these mistakes)

- **Keystore format:** Always generate with `-storetype JKS` explicitly. Java 17's `keytool` default (PKCS12) breaks AGP's signer.
- **Signature continuity:** Never change keystores once a version is in the wild without planning for users to uninstall/reinstall once.
- **OTA source:** Releases, not Actions artifacts. `releases/latest` API is blind to artifacts.
- **R.id compile-time refs:** If adding a new XML id reference in Kotlin, the id must ALREADY exist in the XML before that Kotlin file compiles, or the release build fails outright (debug is more lenient about some things, release is strict). When in doubt, use `resources.getIdentifier(name, "id", packageName)` for forward-compatible soft references, then hard-wire once XML is confirmed updated.
- **`build.yml` artifact step:** Always use dynamic `find ... -name "*.apk"` discovery — hardcoding `Thieves_Trap_vX.X.X_Final.apk` breaks on every version bump.
- **GitHub PAT exposure:** The token has been pasted in many scripts across sessions. Rotate periodically at `github.com/settings/tokens`.
- **`web_fetch` limitation:** Claude cannot fetch raw GitHub URLs for this repo (not search-indexed, blocked by `PERMISSIONS_ERROR`). Must paste file contents manually each session — this STATE.md file is the mitigation.

---

## 8. Version History Summary

| Version | Highlights |
|---|---|
| v2.7.4 → v2.7.5 | SMS priority hardening, intruder selfie via Device Admin, Telegram deep link, Airplane Mode removed, silent grace period, "I'm Safe" no-PIN, language icon moved to sidebar |
| v2.7.6 | Smartwatch Tether feature (full), UI cleanup, IMEI injected into SMS templates |
| v2.7.7 | Static `SmsCommandReceiver`, Smart SIM Trap v1 (had NET_CAPABILITY_VALIDATED freeze bug) |
| v2.7.8 | Coroutine isolation (`SupervisorJob`), lightweight SIM trap (fixed freeze), Plan B PIN commands, build.yml artifact naming fix |
| v2.7.9 | OTA Update feature — `UpdateManager.kt`, sidebar "Check for Update", GitHub Releases API integration |
| v2.7.9b | Fixed duplicate SMS (removed dynamic receiver), restored WHERE footer note, Watch Tether TRIGGER ALARM/DISARM buttons, Plan B info badge, ARM first-time guidance dialog |
| v2.7.10 | OTA test version bump; **discovered + fixed**: debug-vs-release signing mismatch blocking OTA installs |
| v2.8.0 | Watch Tether ℹ️ badge (sidebar symmetry with Survival Timer), Remote Guide command-label bug fixed (every row was showing "WHERE"), copy-to-clipboard button on each command row |

---

## 9. Pending / Not Yet Done

- [ ] MainActivity UI-lag/coroutine optimization for instant shield-color updates on toggle (mentioned once, never delivered — original v2.7.8 request item 4)
- [ ] Verify `AboutActivity.kt` has no hardcoded version strings (last checked: uses `BuildConfig.VERSION_NAME`, should be fine, but not re-verified since v2.7.6)
- [ ] Confirm v2.8.0 build is green and released (last action before this file was created: pushing v2.8.0 patch, not yet confirmed deployed)
- [ ] Rotate GitHub PAT (exposed across many session scripts)

---

## 10. How to Resume Work With Claude

1. Paste this entire STATE.md at the start of the new conversation.
2. State which version you're moving to and what specifically needs to change.
3. If Claude needs to see a specific file's current content (e.g. to make a precise edit), it will ask — paste via `cat path/to/file`.
4. After Claude delivers a patch zip + push script, run it in Termux, then update **Section 8 (Version History)** and **Section 9 (Pending)** in this file before committing it back to the repo.

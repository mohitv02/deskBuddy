# DeskBuddy

A desktop companion for Linux (Ubuntu/GNOME): an animated pet that lives on your screen, a todo list with alarms, an encrypted and searchable vault for passwords and notes, and optional end-to-end encrypted team chat.

> Status: **all five phases done**: floating mascot, todos with alarms, an encrypted and searchable vault, settings, a global shortcut, start on login, and `.deb` / AppImage packages. Team chat is newer and optional.

## Features

- **A pet on your desktop.** Fourteen pets (Buddy, Axolotl, Chibi Cat, Chibi Ninja, Baby Dragon, Ghost, Monkey, Ember, Mochi, Penguin, Fox, Otter, Red Panda, Classic Dragon). They react to your todos, follow your cursor, fall asleep, and can be dragged, thrown and petted. See [assets/PETS.md](assets/PETS.md).
- **Todos with alarms.** Recurring alarms, snooze, and overdue reminders.
- **Encrypted vault.** SQLCipher + Argon2id, full-text search, a clipboard that clears itself, and encrypted backups.
- **Works offline.** No telemetry and no accounts. The only network traffic is the optional chat server, and only if you configure one.
- **Team chat (optional).** End-to-end encrypted direct, team and team-to-team chats through servers you host yourself ([server/](server/)).

## Quick start

On a fresh Ubuntu 22.04+:

```bash
git clone https://github.com/mohitv02/desktopPet.git
cd desktopPet
scripts/setup.sh      # apt packages, Rust (rustup), Node, npm packages
scripts/run.sh        # build and launch
```

To install it instead: run `scripts/package.sh deb`, then `sudo apt install ./<the .deb it prints>`.

> **Rust version.** You need Rust 1.85 or newer from [rustup](https://rustup.rs). Ubuntu's `apt install cargo` (1.75) fails with `lock file version 4 requires -Znext-lockfile-bump`.

The rest of this file is the design log: why each decision was made and how each part works.

## Development environment

Developed and tested on:

| | |
|---|---|
| OS | Ubuntu 22.04.5 LTS |
| Desktop | GNOME Shell 42.9 |
| Session | **X11** (`XDG_SESSION_TYPE=x11`) |
| Displays | DP-1 1920×1080 at +1280+0, HDMI-4 1280×1024 at +0+56, scale 1.0 |

**X11 vs Wayland.** On X11, everything the mascot needs is standard EWMH, and GTK/Tauri handle it reliably: `_NET_WM_STATE_ABOVE` (always on top), `SKIP_TASKBAR`/`SKIP_PAGER`, `STICKY` (all workspaces), self-positioning, and a 32-bit ARGB visual for transparency. GNOME Wayland does not let clients position themselves or stay above other windows. If the app is launched in a Wayland session, `main.rs` sets `GDK_BACKEND=x11`, so it runs under XWayland, where all of the above still works. You can also force this by hand with `GDK_BACKEND=x11 deskbuddy`. A GNOME Shell extension would only be needed if XWayland were unavailable.

## Stack choice

**Tauri 2 (Rust) + TypeScript/React.** It produces a ~4.6 MB binary, uses the system WebKitGTK, and puts the crypto and SQLite code in Rust, where SQLCipher and Argon2id are mature crates. Electron wasn't needed because Tauri's transparent, always-on-top windows behave correctly on this X11 session.

## Architecture

```
src/                         UI (TypeScript)
  lib/ipc.ts                 typed wrappers for every Tauri command
  mascot/                    mascot window: vanilla TS + inline SVG (no React)
    animator.ts              frame animator: rest pose, idle gestures, "happy"
  panel/                     panel window: React (todos / vault / settings)
src-tauri/src/               backend (Rust)
  commands.rs                thin command glue (UI <-> modules)
  settings.rs                non-secret settings JSON, debounced writes
  paths.rs                   XDG paths (~/.config/deskbuddy, ~/.local/share/deskbuddy)
  system/                    window and system-integration module
    window.rs                mascot and panel windows, native mouse input, menu, anchoring, X11 input shape
    single_instance.rs       one instance per user (Unix socket)
    clipboard.rs             GTK clipboard; secrets auto-clear after 30 s
    keyring.rs               todos DB key in the GNOME login keyring
    autolock.rs              locks the vault after idle time
    dialog.rs                native file chooser for backups
    hotkey.rs                global shortcut + GNOME conflict check + tests
    autostart.rs             ~/.config/autostart entry + tests
    fullscreen.rs            event-driven X11 fullscreen detection
  chat.rs                    chat client: login, failover, sync, teams and links
  e2e.rs                     end-to-end encryption (device keys, team keys, archive halves) + tests
  host.rs                    "Host a server" settings: the server's .env and /health
  db/                        data-access layer (all SQL lives here)
    migrations.rs            forward-only migrations via PRAGMA user_version
    chat_keys.rs             this device's identity and team keys + tests
    todos.rs                 todo repository + unit tests
    vault.rs                 vault repository, FTS5 search + unit tests
  mascot.rs                  loads a custom mascot image or sprite sheet
  crypto.rs                  Argon2id KDF, randomness, backup container + tests
  vault_store.rs             vault lock/unlock, master password, rekey + tests
  backup.rs                  encrypted export/import + tests
  legacy.rs                  migrates the Phase 1–3 plaintext database + tests
```

### Mascot window: design decisions

- **Animation.** The mascot is inline SVG redrawn on a 15 fps timer, not Lottie. At idle it holds a rest pose and plays a short gesture (blink, antenna wiggle or bounce) every 2.5 to 6 s, so most of the time no timer runs and nothing is repainted. Completing a todo triggers a 1.5 s "happy" hop with sparkles. The trade-off is that the bob is less smooth than continuous 60 fps, but there's no extra dependency and CPU stays near zero.
- **Pausing.** The animation stops when you pause it from the menu, when the window is hidden, and when the focused window is fullscreen. Fullscreen is detected from `_NET_ACTIVE_WINDOW` and `_NET_WM_STATE_FULLSCREEN`. The watcher thread blocks on X `PropertyNotify` events instead of polling.
- **Click-through.** The X11 *input shape* is set to an ellipse around the mascot (about 56% of the square), so clicks on the transparent corners reach the window underneath. The shape is fixed rather than per-pixel, which keeps runtime cost at zero; the trade-off is that the faint shadow edge isn't clickable.
- **Mouse input is handled natively, not in JavaScript.** GTK signal handlers on the webview widget see each press before WebKit does. A press that moves more than 4 px calls `gtk_window_begin_move_drag` with the real event timestamp, which is what mutter needs for a native move. A press released in place toggles the panel. Right-click opens a native menu built in Rust (Open, Pause animation, Settings, Quit). Two webview-based approaches failed on this machine. Tauri's `startDragging()` called mid-gesture is ignored once GTK holds the pointer grab. Moving the window from JS feeds back into itself, because WebKitGTK's event coordinates are relative to the window. Clicks in this never-focused window were also sometimes lost.
- **Your own mascot.** You can replace the built-in character in two ways. Restart DeskBuddy after adding files. Both are passed to the page as data URLs, so the CSP stays closed to everything else, and each file can be up to 8 MB.
  1. **Single image:** `~/.config/deskbuddy/mascot.png` (or `.gif`, `.webp`, `.svg`, `.jpg`). It keeps the built-in bounce, hop and sparkles.
  2. **Sprite sheet**, for frame-by-frame animation: `~/.config/deskbuddy/mascot/sprite.json` plus the sheet image. This takes priority over a single image.
     ```json
     {
       "image": "sheet.png",
       "frameWidth": 96, "frameHeight": 96,
       "pixelated": false,
       "animations": {
         "idle":  { "start": 0, "frames": 8, "fps": 8, "pauseMs": 2500 },
         "happy": { "start": 8, "frames": 6, "fps": 10 },
         "alarm": { "start": 14, "frames": 4, "fps": 12 }
       },
       "alarmEffect": "flames",
       "effectOrigin": [70, 40]
     }
     ```
     Frames are numbered left to right, then top to bottom, starting at 0. `idle` is required. `happy` is optional and plays when you complete a todo. `alarm` is optional and loops while an alarm rings; without it, the sprite shakes. `alarmEffect` is one of `flames`, `webs`, `shuriken`, `sparks` or `none`, and `effectOrigin` is where the effect starts, in frame pixels: a dragon's mouth, a hand. The default origin is the top centre of the frame. `pauseMs` holds the first idle frame between loops, which keeps CPU low; set it to 0 to loop continuously. Use `"pixelated": true` for pixel art.

     There's a working example (an original character) in `assets/sprite-example/`. Install it with `mkdir -p ~/.config/deskbuddy/mascot && cp assets/sprite-example/* ~/.config/deskbuddy/mascot/`. To regenerate it, run `scripts/make-example-sprite.py`.

     If the manifest is invalid, DeskBuddy logs why and falls back to the built-in character. The `image` value must be a plain file name inside the folder, not a path.
- **Position memory.** `Moved` events update the settings in memory. A background thread writes `~/.config/deskbuddy/settings.json` 500 ms after the last move, so a drag produces one write. A saved position that no longer lies on any monitor resets to the bottom-right corner.

### Todo panel (Phase 2)

- **Storage.** `~/.local/share/deskbuddy/deskbuddy.db`, with the folder at mode 700 and the file at 600. It uses SQLite in WAL mode, built from SQLCipher's sources, so Phase 4 can turn on encryption without swapping libraries.
- **Fields.** title, notes, due (local `YYYY-MM-DD` or `YYYY-MM-DDTHH:MM`), priority (0 to 3), project, status (open, in progress or done), position, created_at and completed_at. The backend validates every field.
- **Views.**
  - **Today**: incomplete todos due today or overdue, followed by the ones completed today.
  - **Pending**: all other incomplete todos.
  - **Completed**: older finished todos, collapsed.

  Today and Pending don't overlap, so no todo appears twice; Pending plus Today together make up "all incomplete".
- **Quick add.** Type in the box and press Enter, or click **+**. **+** with an empty box opens the full form. Quick-add understands `#project`, `!high`/`!med`/`!low` (or `!1` to `!3`), `@today`, `@tomorrow`, `@mon` to `@sun`, `@2026-11-02`, and an optional `HH:MM` after the date. Example: `Pay rent #home !high @tomorrow 09:00`.
- **Editing.** Click a todo to edit every field or delete it (delete asks for confirmation). Ctrl+Enter saves; Esc closes the form, and a second Esc hides the panel.
- **Reordering.** Drag the ⋮⋮ handle, or focus a todo and press Alt+↑ or Alt+↓. Dragging uses pointer events, because HTML5 drag-and-drop is unreliable in WebKitGTK.
- **Feedback.** Overdue todos get a red bar and an "Overdue" label. Completing a todo makes the mascot play its happy animation; the backend emits that event, so it fires whether you tick the box or change the status in the editor.

### Alarms

- **Setting one.** Any todo with a due **time** rings at that time; a date with no time never rings. Examples: `Submit report @today 17:00`, or set a time in the editor. The editor has a "🔔 Ring at …" switch (on by default) and a **Test alarm now** button. Todos with a pending alarm show a 🔔.
- **Evening reminder (17:00).** Once a day at 17:00, DeskBuddy checks the todos in the Today list (due today or overdue) that aren't done and have no alarm left to ring. If there's one, it rings for that todo as usual. If there are several, it rings once with a notification listing them (up to five), with Open and Stop but no Done or Snooze. If DeskBuddy starts between 17:00 and 18:00, it still rings that day. The day it last rang is stored as `eveningReminderDay` in `settings.json`, so a restart doesn't ring it again.
- **When it rings:**
  - A looping alarm sound. It uses `~/.config/deskbuddy/alarm.oga`, `.ogg` or `.wav` if you provide one, otherwise the system alarm sound, played with `paplay`, `pw-play` or `canberra-gtk-play`.
  - A GNOME notification with **Open**, **Mark done** and **Snooze 10 min**.
  - A red banner in the panel with Done, Snooze and Stop.
  - The mascot's alarm animation.
  - A click-through **effect overlay** around the mascot.
- **Stopping it.** Click the mascot, use any notification or banner button, dismiss the notification, or complete the todo. Otherwise it stops by itself after 60 s.
- **How the timing works.**
  - Each alarm rings once; snoozing re-arms it for 10 minutes later.
  - Editing an unrelated field never re-arms an alarm that already rang; changing the time does.
  - Alarms missed while DeskBuddy wasn't running ring at the next start if they are less than 12 h old.
  - A background thread checks every 5 s, so an alarm rings within about 5 s of its time.
- **Effects.** The `alarmEffect` setting in `settings.json` chooses the overlay: `auto` (the default), `sparks`, `flames`, `webs`, `shuriken` or `none`. `auto` uses the sprite's own `alarmEffect`, or `sparks` for the built-in character. The overlay is a separate 600×480 transparent window with an empty input region, so it never blocks clicks. It is created only while an alarm rings and destroyed afterwards, so it costs nothing at idle. It stays on the mascot's monitor, and the effect fires toward the middle of the screen.

### Vault (Phase 3)

- **Entry types.**
  - **VM**: host or IP (required), port, user, SSH key path.
  - Any entry can also have **extra fields**, label and value pairs such as "Logs" → `/var/log/app`. Each shows on the card with its own Copy button, and both label and value are searchable.
  - **Password**: username, website.
  - **API key**: account, service or URL.
  - **Command snippet**.
  - **Note**.

  Every entry has a title, tags, a body or notes field, an optional secret, and created/updated timestamps.
- **Search.** Uses SQLite FTS5 with the `unicode61` tokenizer and prefix indexes. Each word you type must match the start of a word, in any order, so `10.0.3`, `prod-db` and `compose tail` all work. Results are ranked with BM25: title matches first, then tags, then type fields (host, user, URL…), then body. You can filter by type and by tags (an entry must have every tag you select). The search index lives in its own table and is updated in the same transaction as each write.
- **Secrets.**
  - Never indexed, so you can't search for them, and never included in search or list results.
  - **Show** fetches a secret only when clicked and hides it again after 15 s.
  - **Copy** puts it on the clipboard without it passing through the page, and clears it after 30 s. The clear only happens while DeskBuddy still owns the clipboard, so it never wipes something you copied later from another app.
  - When editing, an existing secret is kept unless you choose *change* or *remove*.
  - The Rust `Secret` type prints as `[redacted]`, so a secret can't slip into a log line.
  - Clipboard-history tools, if you have one installed, may still record copies.
- **Notes** show on every card: the first three lines, click to expand.
- **Copy buttons.** Command snippets have a one-click **Copy**. VM entries show and copy the full command, for example `ssh -i ~/.ssh/key -p 2222 user@host`, with shell quoting applied.
- **Storage.** The vault lives in its own SQLCipher-encrypted file, `vault.db`. See Security below.

### Security (Phase 4)

**Two encrypted databases.** Both are SQLCipher files: AES-256 encryption with an HMAC-SHA512 integrity check on every page. Both use a raw 256-bit key, so SQLCipher's own key derivation is skipped.

| File | Key | Unlocked when |
|---|---|---|
| `vault.db` | Argon2id(master password, 16-byte random salt). The defaults are 64 MiB, 3 passes, 1 lane, about 0.5 s to unlock. | You type the master password |
| `deskbuddy.db` (todos) | A random 256-bit key stored in the GNOME login keyring (Secret Service), with a 0600 `todos.key` file as fallback if no keyring is available | You log in |

*Why two files instead of one:* if the whole database needed the master password, todos and alarms would stop working whenever the vault is locked, including after every login until you typed it. Splitting them keeps alarms working while the vault stays properly locked; both files are encrypted at rest.

- **`vault.json`** holds the salt and Argon2id parameters, nothing secret. The parameters are stored so they can be raised later.
- **Locking** (the 🔒 button, or auto-lock after `autoLockMinutes` of no vault activity, 5 by default, 0 = never):
  - closes the database and wipes the key from memory (`zeroize`);
  - `cipher_memory_security` also has SQLCipher wipe its own buffers;
  - the panel switches to the lock screen on its own.
- **Wrong passwords** fail SQLCipher's integrity check. Each failed attempt waits an extra 0.8 s on top of Argon2's cost. SQLCipher's own logging is turned off, so failed attempts aren't written to the log.
- **Changing the master password** generates a new salt and re-encrypts the vault in place. The new parameters are written to `vault.json.next` *before* re-encrypting and renamed over `vault.json` afterwards, so a crash in between still leaves a vault you can open; a unit test simulates exactly that.
- **Backups** (⚙ → Export / Import):
  - One `.dbkp` file holds both databases, each encrypted with Argon2id(backup password, fresh salt).
  - Import checks the backup's integrity before touching anything, re-encrypts it under your current keys, then swaps it in. The previous files are kept as `*.pre-import`.
  - A wrong backup password or a tampered file is rejected and your current data is left untouched (unit-tested).
- **Upgrading from Phases 1–3.** On the first start, an old unencrypted `deskbuddy.db` is moved aside and its todos are encrypted straight away. Its vault entries are encrypted when you create your master password. Then the plaintext file is overwritten with zeros and deleted. On SSDs, old blocks can survive overwriting; the file is removed either way.
- **Nothing is logged that could leak a secret.** Secrets use a `[redacted]` Debug type, and passwords arrive in `Zeroizing` buffers.
- **No network access.** The CSP allows only the app's internal IPC channel. There is no HTTP, TLS or WebSocket crate in the dependency tree. The JS bundle contains no `fetch`, XHR or WebSocket calls; the Vite module-preload polyfill is turned off.
- **Limits.**
  - The master password can't be recovered. Keep a backup.
  - Anyone using your unlocked session can open the panel while the vault is unlocked, which is what auto-lock is for.
  - Clipboard-history tools may record copied secrets.

### Settings, shortcut, start on login (Phase 5)

- **Settings tab.** Every change applies immediately and is saved to `~/.config/deskbuddy/settings.json`:
  - start on login;
  - the panel shortcut;
  - mascot size (48 to 256 px, resized live);
  - animation on/off;
  - alarm effect, with a **Preview** button;
  - vault auto-lock time.
- **Global shortcut: Ctrl+Alt+B by default.** The original spec asked for Ctrl+Alt+T, but Ubuntu uses that to open Terminal, and Ctrl+Alt+D for "show desktop". On X11, grabbing a shortcut the desktop already uses doesn't fail; both programs would react to it. So before registering, DeskBuddy checks the shortcut against GNOME's own keybinding settings (media-keys, wm, shell and mutter) and refuses any it finds there, naming the action that owns it. Older saved defaults are moved to Ctrl+Alt+B automatically. To change the shortcut, click it in Settings and press the new keys.
- **Start on login** writes `~/.config/autostart/deskbuddy.desktop`. At every start, the entry is updated to point at wherever DeskBuddy now lives: `/usr/bin/deskbuddy` after installing the `.deb`, or the AppImage file itself (not its temporary mount point).
- **Notifications** are the alarm notifications described above (Phase 2's "optional reminders").

### Choosing a pet

**Settings → Mascot → Pet → Change ›** lists the built-in Buddy, every bundled pack (Axolotl, Chibi Cat, Chibi Ninja, Baby Dragon, Ghost, Monkey, Ember, Mochi, Penguin, Fox, Otter, Red Panda, Classic Dragon) and, if present, your own files from `~/.config/deskbuddy/`. Picking one swaps it live: the old pet shrinks away and the new one pops in, with no restart. Below the grid, the page shows which clips play for each event (hover, clicks, todo added / started / done / all done / deleted / overdue, alarms, being dragged, sleep, the pointer nearby, …); each clip has a ▶ button that plays it on the desktop. A state can list several clips, and one is picked at random each time. The choice is saved as `pet` in `settings.json`. Drag the pet up and let go, and it drops back down a few inches (the window falls with gravity, at most 200 px and never off the screen), then plays its landing clip. With nothing happening for **Sleep after** (Settings, default 20 seconds) it dozes off. When it's unset, your own files win if you have any, as before.

The packs ship as app resources (`pets/` next to the binary, from `bundle.resources` in `tauri.conf.json`). Each pack's mapping is its `assets/<pack>/mascot.json`. [`assets/PETS.md`](assets/PETS.md) describes every pet's moves, emotions and mapping. After adding or regenerating a pack, run `python3 scripts/prepare-pets.py`: it stamps clip timing from `index.json` onto the SVGs and builds Ember's PNG strips (side and front views) and Mochi's spritesheet into SVG clips.

### State-set mascot (e.g. the axolotl or the dragon)

One self-animating SVG per state lives in `~/.config/deskbuddy/mascot/`, listed in a `mascot.json`. This option takes priority over `sprite.json` and `mascot.png`. The axolotl in `assets/axolotl_pet/` is set up like this:

```json
{
  "type": "svg-states",
  "states": {
    "idle": "idle_breathe.svg", "hover": "int_petted.svg", "doubleClick": "int_tickled.svg",
    "clicks": "int_poked.svg", "done": "mood_happy.svg", "alarm": "mood_surprised.svg",
    "alarmClosed": "mood_smile_wink.svg", "snooze": "idle_yawn.svg", "intro": "move_fall_land.svg",
    "fallAsleep": "sleep_fall_asleep.svg", "sleep": "sleep_loop.svg", "wakeUp": "sleep_wake_up.svg"
  },
  "idleVariants": ["idle_gill_wiggle.svg", "idle_look_left_right.svg", "idle_stretch.svg", "idle_blow_bubbles.svg", "idle_yawn.svg"],
  "sleepAfterSeconds": 120,
  "alarmEffect": "sparks",
  "effectOrigin": [256, 170]
}
```

Install it with the command below, then restart. For the dragon, use `assets/dragon/*` instead.

```bash
rm -rf ~/.config/deskbuddy/mascot && mkdir -p ~/.config/deskbuddy/mascot
cp assets/axolotl_pet/mascot.json assets/axolotl_pet/svg/*.svg ~/.config/deskbuddy/mascot/
```

| State | When | Missing → falls back to |
|---|---|---|
| `idle` (required) | the default | — |
| `hover` | while the pointer is over the mascot | idle |
| `alarm` | while an alarm rings | idle |
| `alarmClosed` | 3 s after an alarm is stopped, completed or dismissed | hover |
| `doubleClick` | 2 s after 2 quick clicks | nothing happens |
| `clicks` | 3 s after 3 quick clicks (only the first click toggles the panel) | alarm |
| `done` | 2.5 s after a todo is completed | hover |
| `snooze` | 4 s after an alarm is snoozed | idle |
| `intro` | once, when DeskBuddy starts (skipped while animation is off) | nothing happens |
| `sleep` | after `sleepAfterSeconds` (default 120, `0` = never) with no hover, click or todo change | never sleeps |
| `fallAsleep` | once, on the way into `sleep` | goes straight to sleep |
| `wakeUp` | once, when a sleeping mascot is clicked, hovered for 1.5 s, or a todo changes. An alarm, completed todo or snooze wakes it straight into that reaction | wakes without a clip |

`idleVariants` (optional) are extra idle clips. One of them plays every 9 to 23 s while the mascot is idle and nothing else is happening.

- **CSS or SMIL.** The SVGs can animate with their own CSS (the dragon) or with SMIL `<animate>` tags (the axolotl). Clips can declare `data-fps`, `data-frames` and `data-loop` on the root `<svg>`, as the axolotl's do.
- **The animations are stepped by hand to keep CPU low.** Left alone, WebKit repaints SVG animations at 60 fps, which measured 9.5% CPU for the dragon. Instead DeskBuddy pauses them and steps them itself. CSS clips step through the Web Animations API, at 6 fps when idle and 24 fps in reactions; measured idle CPU is 1.8% of one core. SMIL clips step with `setCurrentTime` at their own `data-fps`, capped at 30; the axolotl at 128 px measured about 1.3% of one core.
- **Smooth changes.** SMIL clips crossfade into each other over 160 ms. Timed reactions last a whole number of clip cycles (the times in the table are rounded to that), so a move never cuts off halfway. CSS clips swap instantly, because their inlined `<style>` blocks would collide if two were mounted at once.
- **Files are sanitised before use.** Scripts, `foreignObject`, `on*` handlers and external links are removed, and each file can be up to 2 MB.
- **`effectOrigin`** is given in the idle SVG's `viewBox` coordinates: the axolotl's head, the dragon's mouth.
- **Lottie:** both packs also ship Lottie files that render the same as the SVGs. The SVG versions are used, so no Lottie runtime is needed.

### Custom mascot: which files to use

| You have | Use it like this |
|---|---|
| One SVG per state, animated with CSS or SMIL | `mascot.json` state set (see above). It supports hover, alarm, double-click, click-streak, done, snooze and intro reactions, plus random idle variants. |
| A PNG sprite sheet | Write a `sprite.json` (see above). This is the best option: transparency, separate idle, happy and alarm animations, and an effect origin. |
| Animated GIF / WebP / APNG files | `scripts/gif-to-sprite.py idle.gif --happy happy.gif --alarm alarm.gif --effect flames --origin 90,40 --size 128` writes the sheet and `sprite.json` into `~/.config/deskbuddy/mascot/`. Or drop one file in as `mascot.gif`, which gives a single looping image with no separate animations. |
| A static PNG or SVG | Save it as `~/.config/deskbuddy/mascot.png` (or `.svg`). |
| Lottie `.json` | Not supported. It would need a Lottie runtime; export SVGs or a sprite sheet instead. |
| MP4 / video | Not supported. Video has no transparency; export frames or a GIF/WebP with a transparent background instead. |

Restart DeskBuddy after changing mascot files.

### Packaging

```bash
scripts/package.sh            # runs the tests, then builds .deb + AppImage
scripts/package.sh deb        # only the .deb
```

Output goes to `src-tauri/target/release/bundle/`.

- **`.deb`** (about 3.5 MB). Install with `sudo apt install ./src-tauri/target/release/bundle/deb/DeskBuddy_0.1.0_amd64.deb`. It depends on `libwebkit2gtk-4.1-0`, `libgtk-3-0` and `libssl3`; SQLCipher is compiled into the binary. It installs `/usr/bin/deskbuddy`, the icons and an app-menu entry.
- **AppImage** (about 82 MB, because it bundles WebKitGTK). Run it with `chmod +x DeskBuddy_*.AppImage && ./DeskBuddy_*.AppImage`. It needs `libfuse2`. Building it downloads Tauri's linuxdeploy helpers the first time; that's a build-time download only.
- For the alarm sound, either `pulseaudio-utils` (`paplay`) or `pipewire-bin` (`pw-play`) must be installed. Ubuntu Desktop has them by default.

### Measured (release build, idle)

| | |
|---|---|
| CPU, all processes (UI + 2 WebKit + network) | **0.5% of one core** over 40 s |
| CPU before switching to gesture-based idle (continuous 12 fps) | 3.3% |
| Binary size | 4.6 MB |

## Building and running

Build-time system packages (one time):

```bash
sudo apt install -y libwebkit2gtk-4.1-dev libgtk-3-dev libayatana-appindicator3-dev librsvg2-dev libxdo-dev
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh   # Rust toolchain
npm install
```

Tests:

```bash
(cd src-tauri && cargo test)   # crypto, vault lock/rekey, backups, migration, search, todos, alarms, hotkey, autostart (33 tests)
```

Run:

```bash
scripts/run.sh                     # debug build, attached to the terminal
PROFILE=release scripts/run.sh -d  # optimized build, detached (survives closing the terminal)
scripts/run.sh --stop              # quit (or right-click the mascot -> Quit)
```

Only one instance runs per user. Launching again while it's running doesn't start a second mascot; it opens the existing panel through a Unix socket at `$XDG_RUNTIME_DIR/deskbuddy/deskbuddy.sock`.

`scripts/run.sh` exists for two reasons:

1. **The VS Code snap leaks its GTK and library variables** (`GTK_PATH`, `GIO_MODULE_DIR`, `LOCPATH`, …) into its terminal. A host-linked WebKitGTK app that inherits them crashes with `undefined symbol: __libc_pthread_init`. The script unsets them before launching.
2. **`tauri dev` and `tauri build` need inotify watches**, and they fail with "OS file watch limit reached" when editors have used them all (this machine: `max_user_watches=65536`). The script calls `cargo` directly instead. You can also raise the limit:
   `echo fs.inotify.max_user_watches=524288 | sudo tee /etc/sysctl.d/60-inotify.conf && sudo sysctl --system`.

## Chat (optional)

Chat is off until you connect to a server in **Settings → Chat** (type its address, or **Find servers on this network**). You or your team run the server: a small Rust service backed by MongoDB, in [server/](server/). See [server/README.md](server/README.md) for setup and the design.

- **Identity.** Each install has its own key pair; its public key is your device id. The server checks a signature at every login, so nobody can pose as you, and IP addresses no longer matter.
- **End-to-end encryption.** Messages are encrypted in the app (XChaCha20-Poly1305) before they leave it. Servers and their databases only see ciphertext, plus who wrote to whom and when.
- **Direct chats** (＋ in the chat bar) with anyone on the same server, or in a team linked to yours for personal chats.
- **Teams** (👥 in the chat bar). Create a team and share its invite (`DBT1-…`). The invite holds the team key, so send it privately. **New key** removes everyone until they join again with the new invite; use it when someone leaves.
- **Team to team.** Give another team your team's address (`DBA1-…`, safe to share). They send one of three requests: a *group chat* for both teams, a *temporary group* that closes after 1–72 hours, or *personal chats* between members. Any member can accept. Both teams see a safety number: compare it on a call, and if it differs someone swapped the keys.
- **Temporary groups and their archive.** When one closes, its messages leave everyone's app. The archive stays on the servers for the period you chose, or forever. It is encrypted with a key made of two halves, one held by each team, so it can be read again only when **both** teams press *Release our half*. Either team can lock it again.
- **Several servers per team.** Servers that share one MongoDB database act as one; the app learns all of them and switches if one is down. Teams on different databases (different "homes") are connected server to server, and messages wait in a queue while the other side is offline.

Chats from the old IP-based server stay readable but can't be continued.

## Privacy

There's no telemetry. With chat off (the default), the app makes no network connections at all; the CSP allows only `ipc:` connections. With chat on, the Rust side connects only to your chat servers. **Find servers on this network** sends one mDNS query, only when you click it.

## Contributing

Issues and pull requests are welcome; see [CONTRIBUTING.md](CONTRIBUTING.md). Report security problems privately, as described in [SECURITY.md](SECURITY.md).

## License

[Apache License 2.0](LICENSE). Bundled third-party code: `lottie-web` 5.12.2 (MIT) in `assets/chibi_ninja_pet/vendor/`.

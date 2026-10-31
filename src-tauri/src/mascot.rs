//! Mascot artwork. The `pet` setting picks one of:
//!
//! * `classic` — the built-in drawn character (no files)
//! * a bundled pack (`axolotl`, `ember`, …) — the `assets/<folder>/` state sets
//!   shipped as app resources under `pets/`
//! * `custom` — artwork supplied by the user in `~/.config/deskbuddy/`, in
//!   order of precedence:
//!   * `mascot/mascot.json` + SVG files — one self-animating SVG per state
//!     (idle, hover, alarm, …), e.g. a dragon that flies on hover
//!   * `mascot/sprite.json` + its sheet image — frame-based sprite animation
//!   * `mascot.{png,gif,webp,svg,jpg}` — a single (optionally animated) image
//! * `""` (the default) — `custom` if present, else `classic`
//!
//! Files are handed to the page as data URLs so the CSP stays closed.

use std::path::{Component, Path, PathBuf};
use std::sync::OnceLock;

use base64::Engine;
use serde::{Deserialize, Serialize};

use crate::paths;

const MAX_BYTES: u64 = 8 * 1024 * 1024;

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Animation {
    /// First frame, counted left-to-right, top-to-bottom from 0.
    #[serde(default)]
    pub start: u32,
    pub frames: u32,
    #[serde(default = "default_fps")]
    pub fps: f32,
    /// Idle only: hold the first frame this long between loops (keeps CPU low).
    #[serde(default)]
    pub pause_ms: u32,
}

fn default_fps() -> f32 {
    8.0
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Animations {
    pub idle: Animation,
    #[serde(default)]
    pub happy: Option<Animation>,
    /// Loops while an alarm rings (optional; otherwise the sprite shakes).
    #[serde(default)]
    pub alarm: Option<Animation>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SpriteManifest {
    /// Sheet file name, relative to the manifest's folder.
    pub image: String,
    pub frame_width: u32,
    pub frame_height: u32,
    /// Nearest-neighbour scaling for pixel art.
    #[serde(default)]
    pub pixelated: bool,
    pub animations: Animations,
    /// Overlay effect while an alarm rings: "flames", "webs", "shuriken", "sparks", "none".
    #[serde(default)]
    pub alarm_effect: Option<String>,
    /// Where the effect starts, in frame pixels (e.g. a dragon's mouth). Default: top centre.
    #[serde(default)]
    pub effect_origin: Option<[f32; 2]>,
}

pub const EFFECTS: [&str; 5] = ["sparks", "flames", "webs", "shuriken", "none"];

/// States a state-set mascot can define. Only `idle` is required; missing
/// ones fall back (see svgstates.ts).
pub const STATES: [&str; 31] = [
    "idle", "hover", "alarm", "alarmClosed", "clicks", "doubleClick", "done", "snooze", "intro", "fallAsleep", "sleep", "wakeUp",
    // todo moods
    "allDone", "added", "started", "deleted", "overdue", "hungry",
    // being carried around: held, falling after a lift, landing
    "dragged", "falling", "dropped",
    // flung sideways: tumbling along, then back on its feet (clips face right)
    "thrown", "thrownLanded",
    // watching the pointer
    "lookUp", "lookUpRight", "lookRight", "lookDownRight", "lookDown", "lookDownLeft", "lookLeft", "lookUpLeft",
];

/// One clip, or several to pick from at random each time.
#[derive(Debug, Clone, Deserialize)]
#[serde(untagged)]
pub enum Clips {
    One(String),
    Many(Vec<String>),
}

/// A clip entry is a file name, optionally with a start offset in seconds:
/// `move_fall_land.svg@0.45` plays from just before the touchdown.
fn entry_file(entry: &str) -> &str {
    entry.split_once('@').map_or(entry, |(file, _)| file)
}

fn valid_entry(entry: &str) -> bool {
    let offset_ok = entry.split_once('@').map_or(true, |(_, t)| t.parse::<f64>().map_or(false, |t| (0.0..=60.0).contains(&t)));
    let file = entry_file(entry);
    offset_ok && plain_name(file) && file.to_ascii_lowercase().ends_with(".svg")
}

impl Clips {
    pub fn files(&self) -> &[String] {
        match self {
            Clips::One(f) => std::slice::from_ref(f),
            Clips::Many(v) => v,
        }
    }
}
const MAX_SVG_BYTES: u64 = 2 * 1024 * 1024;

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct StatesManifest {
    #[serde(rename = "type")]
    pub kind: String,
    /// Shown in the pet picker.
    #[serde(default)]
    pub name: Option<String>,
    #[serde(default)]
    pub description: Option<String>,
    /// Sub-folder holding the SVGs (bundled packs keep them in `svg/`).
    #[serde(default)]
    pub svg_dir: Option<String>,
    /// state name -> SVG file name in the mascot folder
    pub states: std::collections::BTreeMap<String, Clips>,
    /// Extra idle clips, played now and then between idle loops.
    #[serde(default)]
    pub idle_variants: Vec<String>,
    /// Inactivity before the "sleep" state (default in svgstates.ts; 0 = never).
    #[serde(default)]
    pub sleep_after_seconds: Option<u32>,
    #[serde(default)]
    pub alarm_effect: Option<String>,
    /// Effect start point in the idle SVG's viewBox coordinates.
    #[serde(default)]
    pub effect_origin: Option<[f32; 2]>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(tag = "type", rename_all = "camelCase")]
pub enum CustomMascot {
    Image { url: String },
    Sprite { url: String, sheet: SpriteManifest },
    /// state name -> SVG markup (sanitised again in the page before use)
    #[serde(rename_all = "camelCase")]
    SvgStates {
        /// file name -> SVG markup, each file once
        clips: std::collections::BTreeMap<String, String>,
        /// state -> clip entries to pick from (file name, optionally `@seconds` to start at)
        states: std::collections::BTreeMap<String, Vec<String>>,
        idle_variants: Vec<String>,
        sleep_after_seconds: Option<u32>,
    },
}

fn mime(path: &Path) -> Option<&'static str> {
    match path.extension()?.to_str()?.to_ascii_lowercase().as_str() {
        "png" => Some("image/png"),
        "gif" => Some("image/gif"),
        "webp" => Some("image/webp"),
        "svg" => Some("image/svg+xml"),
        "jpg" | "jpeg" => Some("image/jpeg"),
        _ => None,
    }
}

fn data_url(path: &Path) -> Result<String, String> {
    let mime = mime(path).ok_or_else(|| format!("{}: unsupported image type", path.display()))?;
    let meta = std::fs::metadata(path).map_err(|e| format!("{}: {e}", path.display()))?;
    if meta.len() > MAX_BYTES {
        return Err(format!("{} is larger than 8 MB", path.display()));
    }
    let bytes = std::fs::read(path).map_err(|e| format!("{}: {e}", path.display()))?;
    Ok(format!("data:{mime};base64,{}", base64::engine::general_purpose::STANDARD.encode(bytes)))
}

/// Only plain file names inside the mascot folder (no paths, no `..`).
fn plain_name(name: &str) -> bool {
    let p = Path::new(name);
    p.components().count() == 1 && p.components().all(|c| matches!(c, Component::Normal(_)))
}

fn validate_states(m: &StatesManifest) -> Result<(), String> {
    if m.kind != "svg-states" {
        return Err("mascot.json: \"type\" must be \"svg-states\"".into());
    }
    if !m.states.contains_key("idle") {
        return Err("mascot.json: an \"idle\" state is required".into());
    }
    for state in m.states.keys() {
        if !STATES.contains(&state.as_str()) {
            return Err(format!("mascot.json: unknown state \"{state}\" (use {})", STATES.join(", ")));
        }
    }
    if let Some(dir) = &m.svg_dir {
        if !plain_name(dir) {
            return Err(format!("mascot.json: svgDir \"{dir}\" must be a folder name inside the mascot folder"));
        }
    }
    for clips in m.states.values() {
        if clips.files().is_empty() {
            return Err("mascot.json: a state needs at least one clip".into());
        }
    }
    for file in m.states.values().flat_map(Clips::files).chain(&m.idle_variants) {
        if !valid_entry(file) {
            return Err(format!("mascot.json: \"{file}\" must be an .svg file name inside the mascot folder (optionally @seconds)"));
        }
    }
    if let Some(e) = &m.alarm_effect {
        if !EFFECTS.contains(&e.as_str()) {
            return Err(format!("mascot.json: alarmEffect must be one of {}", EFFECTS.join(", ")));
        }
    }
    Ok(())
}

fn validate(m: &SpriteManifest) -> Result<(), String> {
    if !plain_name(&m.image) {
        return Err("sprite.json: \"image\" must be a file name inside the mascot folder".into());
    }
    if m.frame_width == 0 || m.frame_height == 0 {
        return Err("sprite.json: frameWidth and frameHeight must be > 0".into());
    }
    if let Some(e) = &m.alarm_effect {
        if !EFFECTS.contains(&e.as_str()) {
            return Err(format!("sprite.json: alarmEffect must be one of {}", EFFECTS.join(", ")));
        }
    }
    let anims = std::iter::once(&m.animations.idle).chain(m.animations.happy.as_ref()).chain(m.animations.alarm.as_ref());
    for a in anims {
        if a.frames == 0 || !(a.fps > 0.0 && a.fps <= 60.0) {
            return Err("sprite.json: each animation needs frames >= 1 and 0 < fps <= 60".into());
        }
    }
    Ok(())
}

fn sprite_dir() -> PathBuf {
    paths::config_dir().join("mascot")
}

/// Bundled packs: (setting id, folder under the pets root).
pub const PACKS: [(&str, &str); 13] = [
    ("axolotl", "axolotl_pet"),
    ("cat", "chibi_cat_reactions"),
    ("ninja", "chibi_ninja_pet"),
    ("baby-dragon", "dragon_pet_sprites"),
    ("ghost", "ghost-pet"),
    ("monkey", "monkey-pet"),
    ("ember", "ember_dragon_sprites"),
    ("dragon", "dragon"),
    ("mochi", "mochi_pet"),
    ("penguin", "penguin-pet"),
    ("fox", "fox-desktop-pet"),
    ("otter", "otter-pet"),
    ("red-panda", "red_panda_pet"),
];

static PETS_ROOT: OnceLock<PathBuf> = OnceLock::new();

/// Where the bundled packs live: the app's `pets/` resources, or the repo's
/// `assets/` when running a build that was not bundled.
pub fn init(resource_dir: Option<PathBuf>) {
    let bundled = resource_dir.map(|d| d.join("pets")).filter(|d| d.is_dir());
    let root = bundled.unwrap_or_else(|| Path::new(env!("CARGO_MANIFEST_DIR")).join("../assets"));
    let _ = PETS_ROOT.set(root);
}

fn pack_dir(id: &str) -> Option<PathBuf> {
    let (_, folder) = PACKS.iter().find(|(p, _)| *p == id)?;
    Some(PETS_ROOT.get()?.join(folder))
}

pub fn is_known(id: &str) -> bool {
    id.is_empty() || id == "classic" || id == "custom" || PACKS.iter().any(|(p, _)| *p == id)
}

fn has_custom() -> bool {
    let dir = paths::config_dir();
    sprite_dir().join("mascot.json").is_file()
        || sprite_dir().join("sprite.json").is_file()
        || ["png", "gif", "webp", "svg", "jpg"].iter().any(|ext| dir.join(format!("mascot.{ext}")).is_file())
}

/// The pet actually shown for a `pet` setting.
pub fn resolve(pet: &str) -> String {
    match pet {
        "" if has_custom() => "custom".into(),
        "" => "classic".into(),
        p if is_known(p) => p.into(),
        _ => "classic".into(),
    }
}

/// Just the validated manifest (no image), for alarm effect placement.
pub fn manifest() -> Option<SpriteManifest> {
    let text = std::fs::read_to_string(sprite_dir().join("sprite.json")).ok()?;
    let m: SpriteManifest = serde_json::from_str(&text).ok()?;
    validate(&m).ok().map(|_| m)
}

fn states_manifest(dir: &Path) -> Option<Result<StatesManifest, String>> {
    let text = std::fs::read_to_string(dir.join("mascot.json")).ok()?;
    Some(serde_json::from_str::<StatesManifest>(&text).map_err(|e| format!("mascot.json: {e}")).and_then(|m| validate_states(&m).map(|_| m)))
}

fn read_svg(dir: &Path, m: &StatesManifest, file: &str) -> Result<String, String> {
    let path = m.svg_dir.as_ref().map_or_else(|| dir.join(file), |sub| dir.join(sub).join(file));
    let meta = std::fs::metadata(&path).map_err(|e| format!("{}: {e}", path.display()))?;
    if meta.len() > MAX_SVG_BYTES {
        return Err(format!("{} is larger than 2 MB", path.display()));
    }
    std::fs::read_to_string(&path).map_err(|e| format!("{}: {e}", path.display()))
}

/// `viewBox="minx miny w h"` of an SVG document (default 0 0 100 100).
fn view_box(svg: &str) -> (f64, f64, f64, f64) {
    let parsed = svg.find("viewBox=").and_then(|i| {
        let rest = &svg[i + 8..];
        let quote = rest.chars().next()?;
        let body = &rest[1..rest[1..].find(quote)? + 1];
        let v: Vec<f64> = body.split(|c: char| c == ',' || c.is_whitespace()).filter(|s| !s.is_empty()).filter_map(|s| s.parse().ok()).collect();
        (v.len() == 4 && v[2] > 0.0 && v[3] > 0.0).then(|| (v[0], v[1], v[2], v[3]))
    });
    parsed.unwrap_or((0.0, 0.0, 100.0, 100.0))
}

/// Folder of the state set behind a pet, if it is one.
fn states_dir(pet: &str) -> Option<PathBuf> {
    match resolve(pet).as_str() {
        "classic" => None,
        "custom" => Some(sprite_dir()),
        id => pack_dir(id),
    }
}

/// Whether the current pet has a clip for `state` (state sets only).
pub fn has_state(pet: &str, state: &str) -> bool {
    states_dir(pet).and_then(|dir| states_manifest(&dir)).is_some_and(|m| m.is_ok_and(|m| m.states.contains_key(state)))
}

/// Alarm effect for the current pet: (effect name, origin in px inside a
/// `size`-px mascot window). None = no preference (the built-in character).
pub fn effect_spec(pet: &str, size: f64) -> (Option<String>, Option<(f64, f64)>) {
    let Some(dir) = states_dir(pet) else { return (None, None) };
    if let Some(Ok(m)) = states_manifest(&dir) {
        let origin = m.effect_origin.and_then(|[x, y]| {
            let svg = read_svg(&dir, &m, entry_file(m.states.get("idle")?.files().first()?)).ok()?;
            let (mx, my, w, h) = view_box(&svg);
            // Default preserveAspectRatio: xMidYMid meet.
            let k = (size / w).min(size / h);
            Some(((size - w * k) / 2.0 + (x as f64 - mx) * k, (size - h * k) / 2.0 + (y as f64 - my) * k))
        });
        return (m.alarm_effect, origin);
    }
    if resolve(pet) != "custom" {
        return (None, None);
    }
    if let Some(m) = manifest() {
        let (fw, fh) = (m.frame_width as f64, m.frame_height as f64);
        let k = (size / fw).min(size / fh);
        let [x, y] = m.effect_origin.unwrap_or([fw as f32 / 2.0, fh as f32 * 0.2]);
        // Sprites are scaled to fit and bottom-centred (see sprite.ts).
        return (m.alarm_effect, Some(((size - fw * k) / 2.0 + x as f64 * k, size - fh * k + y as f64 * k)));
    }
    (None, None)
}

fn load_sprite(dir: &Path) -> Option<Result<CustomMascot, String>> {
    let manifest_path = dir.join("sprite.json");
    let text = std::fs::read_to_string(&manifest_path).ok()?;
    Some((|| {
        let sheet: SpriteManifest = serde_json::from_str(&text).map_err(|e| format!("sprite.json: {e}"))?;
        validate(&sheet)?;
        let url = data_url(&dir.join(&sheet.image))?;
        Ok(CustomMascot::Sprite { url, sheet })
    })())
}

fn load_states(dir: &Path) -> Option<Result<CustomMascot, String>> {
    let manifest = match states_manifest(dir)? {
        Ok(m) => m,
        Err(e) => return Some(Err(e)),
    };
    let mut clips = std::collections::BTreeMap::new();
    for entry in manifest.states.values().flat_map(Clips::files).chain(&manifest.idle_variants) {
        let file = entry_file(entry);
        if clips.contains_key(file) {
            continue;
        }
        match read_svg(dir, &manifest, file) {
            Ok(svg) => {
                clips.insert(file.to_string(), svg);
            }
            Err(e) => return Some(Err(e)),
        }
    }
    let states = manifest.states.iter().map(|(k, v)| (k.clone(), v.files().to_vec())).collect();
    let idle_variants = manifest.idle_variants.clone();
    Some(Ok(CustomMascot::SvgStates { clips, states, idle_variants, sleep_after_seconds: manifest.sleep_after_seconds }))
}

fn load_custom() -> Option<CustomMascot> {
    let dir = paths::config_dir();
    if let Some(result) = load_states(&sprite_dir()) {
        match result {
            Ok(m) => return Some(m),
            Err(e) => eprintln!("deskbuddy: ignoring mascot.json: {e}"),
        }
    }
    if let Some(result) = load_sprite(&sprite_dir()) {
        match result {
            Ok(m) => return Some(m),
            Err(e) => eprintln!("deskbuddy: ignoring custom sprite: {e}"),
        }
    }
    ["png", "gif", "webp", "svg", "jpg"].iter().find_map(|ext| {
        let path = dir.join(format!("mascot.{ext}"));
        path.exists().then(|| data_url(&path)).and_then(|r| r.map_err(|e| eprintln!("deskbuddy: {e}")).ok())
    })
    .map(|url| CustomMascot::Image { url })
}

/// Artwork for a `pet` setting; None = the built-in character.
pub fn load(pet: &str) -> Option<CustomMascot> {
    match resolve(pet).as_str() {
        "classic" => None,
        "custom" => load_custom(),
        id => match load_states(&pack_dir(id)?)? {
            Ok(m) => Some(m),
            Err(e) => {
                eprintln!("deskbuddy: pet {id}: {e}");
                None
            }
        },
    }
}

/// One entry of the settings pet picker.
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PetInfo {
    pub id: String,
    pub name: String,
    pub description: String,
    /// Idle SVG markup for the thumbnail (None: the page draws its own).
    pub preview: Option<String>,
    /// state -> clip names (one is picked at random each time).
    pub states: std::collections::BTreeMap<String, Vec<String>>,
    pub idle_variants: Vec<String>,
    pub alarm_effect: Option<String>,
}

/// "a.svg" -> "a", "a.svg@0.45" -> "a@0.45".
fn clip_name(entry: &str) -> String {
    entry.replacen(".svg", "", 1)
}

fn pet_info(id: &str, dir: &Path, fallback_name: &str) -> Option<PetInfo> {
    let m = states_manifest(dir)?.map_err(|e| eprintln!("deskbuddy: pet {id}: {e}")).ok()?;
    Some(PetInfo {
        id: id.into(),
        name: m.name.clone().unwrap_or_else(|| fallback_name.into()),
        description: m.description.clone().unwrap_or_default(),
        preview: read_svg(dir, &m, entry_file(&m.states["idle"].files()[0])).ok(),
        states: m.states.iter().map(|(k, v)| (k.clone(), v.files().iter().map(|f| clip_name(f)).collect())).collect(),
        idle_variants: m.idle_variants.iter().map(|v| clip_name(v)).collect(),
        alarm_effect: m.alarm_effect.clone(),
    })
}

/// Every pet the picker can offer, built-in first.
pub fn list() -> Vec<PetInfo> {
    let mut pets = vec![PetInfo {
        id: "classic".into(),
        name: "Buddy".into(),
        description: "The built-in lightning bug: blinks, wiggles its antenna, hops when you finish a todo.".into(),
        preview: None,
        states: [("idle", "rest + blink / wiggle / bounce"), ("done", "happy hop with sparkles"), ("alarm", "shake and shout")]
            .iter()
            .map(|(k, v)| (k.to_string(), vec![v.to_string()]))
            .collect(),
        idle_variants: vec![],
        alarm_effect: Some("sparks".into()),
    }];
    pets.extend(PACKS.iter().filter_map(|(id, folder)| pet_info(id, &PETS_ROOT.get()?.join(folder), folder)));
    if has_custom() {
        let custom = pet_info("custom", &sprite_dir(), "Custom").unwrap_or_else(|| PetInfo {
            id: "custom".into(),
            name: "Custom".into(),
            description: String::new(),
            preview: None,
            states: Default::default(),
            idle_variants: vec![],
            alarm_effect: None,
        });
        pets.push(PetInfo {
            name: format!("{} (your files)", custom.name),
            description: format!("From {}", paths::config_dir().display()),
            ..custom
        });
    }
    pets
}

#[cfg(test)]
mod tests {
    use super::*;

    fn manifest(json: &str) -> Result<(), String> {
        let m: SpriteManifest = serde_json::from_str(json).map_err(|e| e.to_string())?;
        validate(&m)
    }

    #[test]
    fn manifest_validation() {
        let ok = r#"{"image":"sheet.png","frameWidth":32,"frameHeight":32,
                     "animations":{"idle":{"frames":4,"fps":6,"pauseMs":2000},"happy":{"start":4,"frames":6}}}"#;
        assert!(manifest(ok).is_ok());
        assert!(manifest(&ok.replace("sheet.png", "../secret.png")).is_err(), "no path traversal");
        assert!(manifest(&ok.replace("sheet.png", "/etc/x.png")).is_err(), "no absolute paths");
        assert!(manifest(&ok.replace("\"frameWidth\":32", "\"frameWidth\":0")).is_err());
        assert!(manifest(&ok.replace("\"frames\":4", "\"frames\":0")).is_err());
        assert!(manifest(r#"{"image":"a.png","frameWidth":1,"frameHeight":1,"animations":{}}"#).is_err(), "idle is required");
        let fx = ok.replacen('{', r#"{"alarmEffect":"flames","effectOrigin":[30,12],"#, 1);
        assert!(manifest(&fx).is_ok());
        assert!(manifest(&fx.replace("flames", "lasers")).is_err(), "unknown effect");
    }

    fn states(json: &str) -> Result<(), String> {
        validate_states(&serde_json::from_str(json).map_err(|e| e.to_string())?)
    }

    #[test]
    fn states_manifest_validation_and_view_box() {
        let ok = r#"{"type":"svg-states","states":{"idle":"happy.svg","hover":"fly.svg"},"alarmEffect":"flames","effectOrigin":[400,420]}"#;
        assert!(states(ok).is_ok());
        assert!(states(&ok.replace("\"idle\"", "\"rest\"")).is_err(), "idle required / unknown state");
        assert!(states(&ok.replace("happy.svg", "../happy.svg")).is_err(), "no traversal");
        assert!(states(&ok.replace("happy.svg", "happy.png")).is_err(), "svg only");
        assert!(states(&ok.replace("svg-states", "lottie")).is_err());
        let variants = ok.replacen('{', r#"{"idleVariants":["yawn.svg"],"#, 1);
        assert!(states(&variants).is_ok());
        assert!(states(&variants.replace("yawn.svg", "../yawn.svg")).is_err(), "variants: no traversal");
        assert!(states(&ok.replace("\"hover\"", "\"doubleClick\"")).is_ok());
        assert!(states(&ok.replace("\"fly.svg\"", "[\"fly.svg\",\"sad.svg\"]")).is_ok(), "clip lists");
        assert!(states(&ok.replace("\"fly.svg\"", "[]")).is_err(), "empty list");
        assert!(states(&ok.replace("fly.svg", "fly.svg@0.45")).is_ok(), "start offset");
        assert!(states(&ok.replace("fly.svg", "fly.svg@soon")).is_err(), "bad offset");
        assert!(states(&ok.replace("\"fly.svg\"", "[\"../x.svg\"]")).is_err(), "lists: no traversal");
        assert!(states(&ok.replace("\"hover\"", "\"sleep\"").replacen('{', r#"{"sleepAfterSeconds":60,"#, 1)).is_ok());
        // The bundled packs must stay installable as-is.
        for (_, pack) in PACKS {
            let text = std::fs::read_to_string(format!("{}/../assets/{pack}/mascot.json", env!("CARGO_MANIFEST_DIR"))).unwrap();
            assert!(states(&text).is_ok(), "assets/{pack}/mascot.json");
        }
        assert_eq!(view_box(r#"<svg viewBox="0 0 800 800">"#), (0.0, 0.0, 800.0, 800.0));
        assert_eq!(view_box("<svg viewBox='-10,5 20 40'>"), (-10.0, 5.0, 20.0, 40.0));
        assert_eq!(view_box("<svg>"), (0.0, 0.0, 100.0, 100.0));
    }

    #[test]
    fn bundled_pets_load() {
        init(None);
        let pets = list();
        for (id, _) in PACKS {
            let info = pets.iter().find(|p| p.id == id).unwrap_or_else(|| panic!("{id} missing from list"));
            assert!(info.preview.is_some(), "{id}: idle preview");
            assert!(matches!(load(id), Some(CustomMascot::SvgStates { .. })), "{id}: loads");
        }
        assert!(load("classic").is_none());
        assert!(is_known("") && is_known("ember") && !is_known("../x"));
    }
}

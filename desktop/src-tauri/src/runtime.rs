//! First-run bootstrap of the engine runtime (ADR-006).
//!
//! Release builds run the engine from a virtual environment in
//! `%LOCALAPPDATA%\Cover_Maker\runtime` (`~/Library/Application
//! Support/Cover_Maker/runtime` on macOS, ADR-013), created with the bundled
//! `uv` from the bundled engine wheel and `pylock.*.toml` lock files:
//!
//! - Phase A (core) blocks the engine start: Python 3.12, the venv with the
//!   engine and its core dependencies, ffmpeg and deno.
//! - Phase B (separation) runs in the background once the engine is up:
//!   PyTorch (CUDA cu128 when the GPU supports it, CPU otherwise; on macOS the
//!   build with Metal) and the separation extra. Downloads stay in the uv
//!   cache, so a retry resumes.
//!
//! A phase is redone when the app version changes, which re-syncs the venv
//! with the lock files of the update. Development builds skip all of this and
//! run the repository engine through `uv run`.

use std::fs;
use std::io::{BufRead, BufReader, Read, Write};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::Mutex;

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

use crate::platform;

/// Lowest compute capability supported by the cu128 PyTorch wheels.
const MIN_CUDA_CAPABILITY: f32 = 7.5;

/// Where the bundled files are and where the runtime goes.
#[derive(Clone, Debug)]
pub struct Layout {
    /// Bundled files (`bundle\` in the install folder, `Contents/Resources/
    /// bundle` in the macOS app): `uv`, the wheel, `pylock.*.toml` and
    /// `deps.json`.
    pub bundle: PathBuf,
    /// `runtime` in the engine data folder (`data_home`).
    pub root: PathBuf,
    pub app_version: String,
}

impl Layout {
    pub fn venv(&self) -> PathBuf {
        self.root.join("venv")
    }

    pub fn bin(&self) -> PathBuf {
        self.root.join("bin")
    }

    pub fn engine_exe(&self) -> PathBuf {
        self.venv()
            .join(platform::VENV_BIN)
            .join(platform::exe("cover-maker"))
    }

    fn python(&self) -> PathBuf {
        self.venv()
            .join(platform::VENV_BIN)
            .join(platform::exe("python"))
    }

    fn uv(&self) -> PathBuf {
        self.bundle.join(platform::exe("uv"))
    }

    fn state_file(&self) -> PathBuf {
        self.root.join("state.json")
    }

    fn wheel(&self) -> Result<PathBuf, String> {
        fs::read_dir(&self.bundle)
            .map_err(|e| format!("cannot read the bundled runtime files: {e}"))?
            .filter_map(Result::ok)
            .map(|entry| entry.path())
            .find(|path| path.extension().is_some_and(|ext| ext == "whl"))
            .ok_or_else(|| "the engine wheel is missing from the installation".into())
    }

    fn lock(&self, profile: &str) -> PathBuf {
        self.bundle.join(format!("pylock.{profile}.toml"))
    }

    /// `PATH` for the engine: the runtime tools (ffmpeg, deno) first, then
    /// the inherited `PATH` and the platform's fallback folders.
    pub fn path_env(&self) -> std::ffi::OsString {
        let mut paths = vec![self.bin()];
        if let Some(current) = std::env::var_os("PATH") {
            paths.extend(std::env::split_paths(&current));
        }
        for dir in platform::fallback_tool_dirs() {
            if !paths.contains(&dir) {
                paths.push(dir);
            }
        }
        std::env::join_paths(paths).unwrap_or_default()
    }
}

/// Engine data folder (`paths.py`): `Cover_Maker` for the installed app,
/// `Cover_Maker.dev` for development builds, so they never share data, in
/// the platform's per-user data folder.
pub fn data_home(development: bool) -> PathBuf {
    platform::local_data_dir().join(if development {
        "Cover_Maker.dev"
    } else {
        "Cover_Maker"
    })
}

/// Default runtime folder, next to the engine data (`paths.py`).
pub fn default_root() -> PathBuf {
    data_home(false).join("runtime")
}

/// What has been installed, persisted in `state.json`.
#[derive(Clone, Debug, Default, PartialEq, Serialize, Deserialize)]
pub struct InstallState {
    /// App version whose core lock is installed.
    pub core: Option<String>,
    /// App version whose separation lock is installed.
    pub separation: Option<String>,
    /// PyTorch build of the separation runtime: `cpu` or `cu128`.
    pub torch: Option<String>,
}

fn load_state(layout: &Layout) -> InstallState {
    fs::read_to_string(layout.state_file())
        .map(|text| parse_state(&text))
        .unwrap_or_default()
}

/// Tolerates a UTF-8 BOM (Windows PowerShell 5.1 adds one when the file is
/// edited by hand); an unreadable file means nothing is installed.
fn parse_state(text: &str) -> InstallState {
    serde_json::from_str(text.trim_start_matches('\u{feff}')).unwrap_or_default()
}

fn save_state(layout: &Layout, state: &InstallState) -> Result<(), String> {
    let text = serde_json::to_string_pretty(state).map_err(|e| e.to_string())?;
    fs::write(layout.state_file(), text).map_err(|e| format!("cannot save runtime state: {e}"))
}

/// Progress of one phase, as shown by the UI.
#[derive(Clone, Debug, Default, Serialize)]
pub struct PhaseStatus {
    /// `pending`, `running`, `done` or `failed`.
    pub state: &'static str,
    pub step: String,
    pub index: u32,
    pub total: u32,
    /// Fraction of the current download, when known.
    pub fraction: Option<f32>,
    /// Last line printed by the current step.
    pub detail: String,
    pub error: String,
}

impl PhaseStatus {
    fn pending() -> Self {
        Self {
            state: "pending",
            ..Self::default()
        }
    }

    fn done() -> Self {
        Self {
            state: "done",
            ..Self::default()
        }
    }
}

#[derive(Clone, Debug, Serialize)]
pub struct BootstrapStatus {
    /// `development` (repository engine) or `runtime` (installed app).
    pub mode: &'static str,
    pub core: PhaseStatus,
    pub separation: PhaseStatus,
    /// PyTorch build being installed or installed.
    pub torch: Option<String>,
    /// What the runtime downloads and uses on disk, when known.
    pub space: Option<DiskPlan>,
}

/// Download and disk space of the runtime for this machine's PyTorch build.
#[derive(Clone, Debug, PartialEq, Serialize)]
pub struct DiskPlan {
    pub torch: String,
    pub download_bytes: u64,
    /// Estimated size of the installed runtime.
    pub disk_bytes: u64,
    /// Still needed: the estimate minus what is already in the runtime folder.
    pub needed_bytes: u64,
    /// Free space on the runtime's drive, when it can be read.
    pub free_bytes: Option<u64>,
    pub folder: String,
}

impl DiskPlan {
    /// Room for the runtime plus a margin for temporary files.
    pub fn fits(&self) -> bool {
        self.free_bytes
            .is_none_or(|free| free >= self.needed_bytes + SPACE_MARGIN)
    }
}

/// Head room kept free on top of the runtime estimate (512 MiB).
const SPACE_MARGIN: u64 = 512 * 1024 * 1024;

#[derive(Debug, Deserialize)]
struct ProfileSize {
    download_bytes: u64,
    disk_bytes: u64,
}

/// `sizes.json` (written by `desktop/scripts/runtime_sizes.py`): per profile.
fn load_sizes(layout: &Layout) -> Option<std::collections::HashMap<String, ProfileSize>> {
    let text = fs::read_to_string(layout.bundle.join("sizes.json")).ok()?;
    serde_json::from_str(text.trim_start_matches('\u{feff}')).ok()
}

/// Total size of the files under `dir` (0 when it does not exist).
pub fn folder_bytes(dir: &Path) -> u64 {
    let Ok(entries) = fs::read_dir(dir) else {
        return 0;
    };
    entries
        .filter_map(Result::ok)
        .map(|entry| match entry.file_type() {
            Ok(kind) if kind.is_dir() => folder_bytes(&entry.path()),
            Ok(_) => entry.metadata().map(|m| m.len()).unwrap_or(0),
            Err(_) => 0,
        })
        .sum()
}

/// Free bytes on the drive that holds `path` (or its nearest existing parent).
pub fn free_bytes(path: &Path) -> Option<u64> {
    let existing = path.ancestors().find(|p| p.exists())?;
    platform::free_bytes(existing)
}

/// The runtime's space needs for `torch`, or `None` without `sizes.json`.
pub fn disk_plan(layout: &Layout, torch: &str) -> Option<DiskPlan> {
    let sizes = load_sizes(layout)?;
    let profile = sizes.get(torch)?;
    let present = folder_bytes(&layout.root);
    Some(DiskPlan {
        torch: torch.to_string(),
        download_bytes: profile.download_bytes,
        disk_bytes: profile.disk_bytes,
        needed_bytes: profile.disk_bytes.saturating_sub(present),
        free_bytes: free_bytes(&layout.root),
        folder: layout.root.display().to_string(),
    })
}

/// True on a first run: nothing of the runtime is installed yet.
pub fn first_run(layout: &Layout) -> bool {
    load_state(layout).core.is_none()
}

impl BootstrapStatus {
    pub fn development() -> Self {
        Self {
            mode: "development",
            core: PhaseStatus::done(),
            separation: PhaseStatus::done(),
            torch: None,
            space: None,
        }
    }

    pub fn runtime() -> Self {
        Self {
            mode: "runtime",
            core: PhaseStatus::pending(),
            separation: PhaseStatus::pending(),
            torch: None,
            space: None,
        }
    }

    /// First run: show the space plan and wait until the user starts it.
    pub fn awaiting_consent(plan: Option<DiskPlan>) -> Self {
        let mut status = Self::runtime();
        status.core.state = "consent";
        status.torch = plan.as_ref().map(|p| p.torch.clone());
        status.space = plan;
        status
    }
}

pub struct BootstrapState(pub Mutex<BootstrapStatus>);

/// Receives every status change (the shell forwards it to the UI).
pub type Notify = dyn Fn(&BootstrapStatus) + Send + Sync;

/// Mutates the shared status and notifies the UI.
struct Reporter<'a> {
    state: &'a BootstrapState,
    notify: &'a Notify,
    separation: bool,
}

impl Reporter<'_> {
    fn update(&self, change: impl FnOnce(&mut PhaseStatus, &mut Option<String>)) {
        let Ok(mut status) = self.state.0.lock() else {
            return;
        };
        let BootstrapStatus {
            core,
            separation,
            torch,
            ..
        } = &mut *status;
        change(if self.separation { separation } else { core }, torch);
        (self.notify)(&status);
    }

    fn step(&self, index: u32, total: u32, step: &str) {
        self.update(|phase, _| {
            phase.state = "running";
            phase.index = index;
            phase.total = total;
            phase.step = step.into();
            phase.fraction = None;
            phase.detail.clear();
            phase.error.clear();
        });
    }

    fn detail(&self, line: &str) {
        self.update(|phase, _| phase.detail = line.into());
    }

    fn fraction(&self, value: f32) {
        self.update(|phase, _| phase.fraction = Some(value));
    }

    fn space(&self, plan: Option<DiskPlan>) {
        let Ok(mut status) = self.state.0.lock() else {
            return;
        };
        status.space = plan;
        (self.notify)(&status);
    }

    fn finish(&self, result: &Result<(), String>) {
        self.update(|phase, _| match result {
            Ok(()) => *phase = PhaseStatus::done(),
            Err(error) => {
                phase.state = "failed";
                phase.error = error.clone();
            }
        });
    }
}

fn hidden(command: &mut Command) -> &mut Command {
    platform::hide_window(command)
}

/// Run the bundled uv with the runtime's own cache and Python folders.
fn uv(layout: &Layout, args: &[&std::ffi::OsStr], report: &Reporter) -> Result<(), String> {
    let mut command = Command::new(layout.uv());
    command
        .args(args)
        .env("UV_CACHE_DIR", layout.root.join("cache"))
        .env("UV_PYTHON_INSTALL_DIR", layout.root.join("python"))
        .env("UV_PYTHON_PREFERENCE", "only-managed")
        .env("UV_NO_CONFIG", "1")
        .env("NO_COLOR", "1")
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    let mut child = hidden(&mut command)
        .spawn()
        .map_err(|e| format!("cannot run uv: {e}"))?;

    let stdout = child.stdout.take().ok_or("uv stdout unavailable")?;
    let drain =
        std::thread::spawn(move || BufReader::new(stdout).lines().map_while(Result::ok).count());
    let mut last = String::new();
    if let Some(stderr) = child.stderr.take() {
        for line in BufReader::new(stderr).lines().map_while(Result::ok) {
            let line = line.trim().to_string();
            if !line.is_empty() {
                report.detail(&line);
                last = line;
            }
        }
    }
    let _ = drain.join();
    let status = child.wait().map_err(|e| e.to_string())?;
    if status.success() {
        Ok(())
    } else {
        Err(format!("uv failed ({status}): {last}"))
    }
}

/// Pinned download from `deps.json`.
#[derive(Clone, Debug, Deserialize)]
pub struct Download {
    pub version: String,
    pub file: String,
    pub urls: Vec<String>,
    pub sha256: String,
}

/// One platform's tools in `deps.json`. `ffmpeg` may be `null` for a platform
/// whose runtime installs none: the engine then uses one on `PATH`.
#[derive(Debug, Deserialize)]
struct Deps {
    ffmpeg: Option<Download>,
    deno: Download,
}

impl Deps {
    /// The tools to install into `bin/`, in order.
    fn tools(&self) -> Vec<(&'static str, &Download)> {
        let mut tools = Vec::new();
        if let Some(ffmpeg) = &self.ffmpeg {
            tools.push(("ffmpeg", ffmpeg));
        }
        tools.push(("deno", &self.deno));
        tools
    }
}

fn load_deps(layout: &Layout) -> Result<Deps, String> {
    let text = fs::read_to_string(layout.bundle.join("deps.json"))
        .map_err(|e| format!("cannot read deps.json: {e}"))?;
    parse_deps(&text, platform::DEPS_KEY)
}

/// `deps.json` holds the pinned downloads of every platform, by key.
fn parse_deps(text: &str, key: &str) -> Result<Deps, String> {
    let mut all: std::collections::HashMap<String, Deps> =
        serde_json::from_str(text).map_err(|e| format!("invalid deps.json: {e}"))?;
    all.remove(key)
        .ok_or_else(|| format!("deps.json has no downloads for {key}"))
}

pub fn sha256_hex(bytes: &[u8]) -> String {
    Sha256::digest(bytes)
        .iter()
        .map(|b| format!("{b:02x}"))
        .collect()
}

fn fetch(url: &str, report: &Reporter) -> Result<Vec<u8>, String> {
    let response = ureq::get(url).call().map_err(|e| e.to_string())?;
    let total = response
        .headers()
        .get("content-length")
        .and_then(|value| value.to_str().ok())
        .and_then(|value| value.parse::<u64>().ok());
    let mut reader = response.into_body().into_reader();
    let mut bytes = Vec::with_capacity(total.unwrap_or(0) as usize);
    let mut chunk = vec![0u8; 1 << 16];
    let mut last_reported = 0.0;
    loop {
        let read = reader.read(&mut chunk).map_err(|e| e.to_string())?;
        if read == 0 {
            break;
        }
        bytes.extend_from_slice(&chunk[..read]);
        if let Some(total) = total {
            let fraction = bytes.len() as f32 / total as f32;
            if fraction - last_reported >= 0.01 {
                report.fraction(fraction);
                last_reported = fraction;
            }
        }
    }
    Ok(bytes)
}

/// Download a pinned archive, trying each mirror until one matches the hash.
fn download(dep: &Download, app_version: &str, report: &Reporter) -> Result<Vec<u8>, String> {
    let mut errors = Vec::new();
    for url in &dep.urls {
        let url = url.replace("{version}", app_version);
        report.detail(&url);
        match fetch(&url, report) {
            Ok(bytes) if sha256_hex(&bytes) == dep.sha256 => return Ok(bytes),
            Ok(_) => errors.push(format!("{url}: checksum mismatch")),
            Err(error) => errors.push(format!("{url}: {error}")),
        }
    }
    Err(format!(
        "could not download {}: {}",
        dep.file,
        errors.join("; ")
    ))
}

/// Extract the files of `bin/` folders (or the archive root) into `target`.
fn extract_bin(archive: &[u8], target: &Path) -> Result<(), String> {
    let mut zip = zip::ZipArchive::new(std::io::Cursor::new(archive))
        .map_err(|e| format!("invalid archive: {e}"))?;
    fs::create_dir_all(target).map_err(|e| e.to_string())?;
    for index in 0..zip.len() {
        let mut entry = zip.by_index(index).map_err(|e| e.to_string())?;
        if entry.is_dir() {
            continue;
        }
        let Some(path) = entry.enclosed_name() else {
            continue;
        };
        let parts: Vec<_> = path.components().collect();
        let in_bin = parts.len() >= 2 && parts[parts.len() - 2].as_os_str() == "bin";
        if !(in_bin || parts.len() == 1) {
            continue;
        }
        let name = path.file_name().ok_or("archive entry without name")?;
        let destination = target.join(name);
        let mut file = fs::File::create(&destination).map_err(|e| e.to_string())?;
        std::io::copy(&mut entry, &mut file).map_err(|e| e.to_string())?;
        file.flush().map_err(|e| e.to_string())?;
        platform::make_executable(&destination).map_err(|e| e.to_string())?;
    }
    Ok(())
}

/// Copy the licence files of an archive (`LICENSE*`, `COPYING*`, at any depth)
/// into `target`: the LGPL asks for its text to travel with the ffmpeg build.
fn extract_licences(archive: &[u8], target: &Path) -> Result<usize, String> {
    let mut zip = zip::ZipArchive::new(std::io::Cursor::new(archive))
        .map_err(|e| format!("invalid archive: {e}"))?;
    let mut copied = 0;
    for index in 0..zip.len() {
        let mut entry = zip.by_index(index).map_err(|e| e.to_string())?;
        let Some(path) = entry.enclosed_name() else {
            continue;
        };
        let Some(name) = path.file_name().and_then(|n| n.to_str()) else {
            continue;
        };
        let upper = name.to_ascii_uppercase();
        if entry.is_dir() || !(upper.starts_with("LICENSE") || upper.starts_with("COPYING")) {
            continue;
        }
        fs::create_dir_all(target).map_err(|e| e.to_string())?;
        let mut file = fs::File::create(target.join(name)).map_err(|e| e.to_string())?;
        std::io::copy(&mut entry, &mut file).map_err(|e| e.to_string())?;
        copied += 1;
    }
    Ok(copied)
}

/// Install a pinned tool into `bin/` unless that exact build is there; its
/// licence files go to `licenses/<name>/`.
fn install_tool(
    layout: &Layout,
    name: &str,
    dep: &Download,
    report: &Reporter,
) -> Result<(), String> {
    let marker = layout.bin().join(format!(".{name}-{}", dep.sha256));
    if marker.exists() {
        return Ok(());
    }
    let archive = download(dep, &layout.app_version, report)?;
    extract_bin(&archive, &layout.bin())?;
    extract_licences(&archive, &layout.root.join("licenses").join(name))?;
    fs::write(&marker, &dep.version).map_err(|e| e.to_string())
}

fn os(value: &str) -> &std::ffi::OsStr {
    std::ffi::OsStr::new(value)
}

/// Phase A: everything the engine needs to start. Idempotent.
pub fn ensure_core(layout: &Layout, state: &BootstrapState, notify: &Notify) -> Result<(), String> {
    let report = Reporter {
        state,
        notify,
        separation: false,
    };
    let result = core_steps(layout, &report);
    report.finish(&result);
    result
}

fn core_steps(layout: &Layout, report: &Reporter) -> Result<(), String> {
    let mut installed = load_state(layout);
    report.update(|_, torch| *torch = installed.torch.clone());
    let current = installed.core.as_deref() == Some(layout.app_version.as_str());
    let deps = load_deps(layout)?;
    let tools = deps.tools();
    if current && layout.engine_exe().exists() {
        for (name, dep) in &tools {
            install_tool(layout, name, dep, report)?;
        }
        return Ok(());
    }
    // Check the room for the whole runtime (PyTorch included) before the
    // first download, so a full disk fails here and not halfway through.
    let torch = installed.torch.clone().unwrap_or_else(torch_build);
    let plan = disk_plan(layout, &torch);
    report.space(plan.clone());
    if let Some(plan) = plan.filter(|p| !p.fits()) {
        return Err(format!(
            "not enough disk space: the runtime needs about {} MiB more, {} MiB are free",
            plan.needed_bytes / (1024 * 1024),
            plan.free_bytes.unwrap_or(0) / (1024 * 1024)
        ));
    }
    fs::create_dir_all(&layout.root).map_err(|e| format!("cannot create runtime folder: {e}"))?;
    let venv = layout.venv();
    let total = 3 + tools.len() as u32;

    report.step(1, total, "python");
    uv(layout, &[os("python"), os("install"), os("3.12")], report)?;

    report.step(2, total, "venv");
    if !layout.python().exists() {
        uv(
            layout,
            &[os("venv"), os("--python"), os("3.12"), venv.as_os_str()],
            report,
        )?;
    }

    // After an update keep the separation runtime: sync with its lock, which
    // includes the core packages, instead of removing it.
    report.step(3, total, "engine");
    let profile = match (&installed.separation, &installed.torch) {
        (Some(_), Some(torch)) => torch.clone(),
        _ => "core".to_string(),
    };
    let lock = layout.lock(&profile);
    uv(
        layout,
        &[
            os("pip"),
            os("sync"),
            os("--python"),
            venv.as_os_str(),
            lock.as_os_str(),
        ],
        report,
    )?;
    let wheel = layout.wheel()?;
    uv(
        layout,
        &[
            os("pip"),
            os("install"),
            os("--no-deps"),
            os("--reinstall"),
            os("--python"),
            venv.as_os_str(),
            wheel.as_os_str(),
        ],
        report,
    )?;

    for (index, (name, dep)) in (4..).zip(&tools) {
        report.step(index, total, name);
        install_tool(layout, name, dep, report)?;
    }

    installed.core = Some(layout.app_version.clone());
    if profile != "core" {
        installed.separation = Some(layout.app_version.clone());
    } else {
        installed.separation = None;
    }
    save_state(layout, &installed)
}

/// PyTorch build for this machine: `COVER_MAKER_TORCH` overrides detection.
/// macOS has one build (Metal, which also runs on the CPU).
pub fn torch_build() -> String {
    if let Ok(forced) = std::env::var("COVER_MAKER_TORCH")
        && platform::TORCH_BUILDS.contains(&forced.as_str())
    {
        return forced;
    }
    if cfg!(target_os = "macos") {
        return platform::TORCH_BUILDS[0].to_string();
    }
    let mut command = Command::new("nvidia-smi");
    command.args(["--query-gpu=compute_cap", "--format=csv,noheader"]);
    let capability = hidden(&mut command)
        .output()
        .ok()
        .filter(|output| output.status.success())
        .map(|output| String::from_utf8_lossy(&output.stdout).into_owned());
    torch_for_capability(capability.as_deref()).to_string()
}

/// `cu128` when any GPU reports a compute capability of at least 7.5.
pub fn torch_for_capability(nvidia_smi: Option<&str>) -> &'static str {
    let supported = nvidia_smi
        .unwrap_or_default()
        .lines()
        .filter_map(|line| line.trim().parse::<f32>().ok())
        .any(|capability| capability >= MIN_CUDA_CAPABILITY);
    if supported { "cu128" } else { "cpu" }
}

/// Phase B: PyTorch and the separation extra, in the background. Idempotent.
pub fn ensure_separation(
    layout: &Layout,
    state: &BootstrapState,
    notify: &Notify,
) -> Result<(), String> {
    let report = Reporter {
        state,
        notify,
        separation: true,
    };
    let result = separation_steps(layout, &report);
    report.finish(&result);
    result
}

fn separation_steps(layout: &Layout, report: &Reporter) -> Result<(), String> {
    let mut installed = load_state(layout);
    if installed.separation.as_deref() == Some(layout.app_version.as_str()) {
        return Ok(());
    }
    let torch = installed.torch.clone().unwrap_or_else(torch_build);
    report.update(|_, current| *current = Some(torch.clone()));
    report.step(1, 1, "separation");
    // `install`, not `sync`: the engine is running from this venv and its own
    // package must stay. The lock pins every package by URL and hash.
    let lock = layout.lock(&torch);
    let venv = layout.venv();
    uv(
        layout,
        &[
            os("pip"),
            os("install"),
            os("--python"),
            venv.as_os_str(),
            os("-r"),
            lock.as_os_str(),
        ],
        report,
    )?;
    installed.torch = Some(torch);
    installed.separation = Some(layout.app_version.clone());
    save_state(layout, &installed)
}

/// Installed and newest yt-dlp versions.
#[derive(Clone, Debug, Serialize)]
pub struct YtDlpVersions {
    pub installed: String,
    pub latest: String,
}

fn installed_ytdlp(layout: &Layout) -> Result<String, String> {
    let mut command = Command::new(layout.python());
    command.args(["-c", "import yt_dlp.version as v; print(v.__version__)"]);
    let output = hidden(&mut command)
        .output()
        .map_err(|e| format!("cannot run the runtime Python: {e}"))?;
    if !output.status.success() {
        return Err("yt-dlp is not installed in the runtime".into());
    }
    Ok(String::from_utf8_lossy(&output.stdout).trim().to_string())
}

fn latest_ytdlp() -> Result<String, String> {
    #[derive(Deserialize)]
    struct Info {
        version: String,
    }
    #[derive(Deserialize)]
    struct Project {
        info: Info,
    }
    let project: Project = ureq::get("https://pypi.org/pypi/yt-dlp/json")
        .call()
        .map_err(|e| format!("cannot reach PyPI: {e}"))?
        .into_body()
        .read_json()
        .map_err(|e| format!("unexpected PyPI answer: {e}"))?;
    Ok(project.info.version)
}

pub fn check_ytdlp(layout: &Layout) -> Result<YtDlpVersions, String> {
    Ok(YtDlpVersions {
        installed: installed_ytdlp(layout)?,
        latest: latest_ytdlp()?,
    })
}

/// Upgrade yt-dlp in the runtime (pure Python, safe while the engine runs;
/// the engine picks it up after a restart).
pub fn update_ytdlp(
    layout: &Layout,
    state: &BootstrapState,
    notify: &Notify,
) -> Result<String, String> {
    let report = Reporter {
        state,
        notify,
        separation: false,
    };
    let venv = layout.venv();
    uv(
        layout,
        &[
            os("pip"),
            os("install"),
            os("--upgrade"),
            os("--python"),
            venv.as_os_str(),
            // Not `yt-dlp[default]`: that extra pulls in mutagen (GPL), which
            // the engine does not use (see engine/pyproject.toml).
            os("yt-dlp"),
            os("yt-dlp-ejs"),
        ],
        &report,
    )?;
    installed_ytdlp(layout)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn picks_cuda_only_for_supported_gpus() {
        assert_eq!(torch_for_capability(Some("8.6\n")), "cu128");
        assert_eq!(torch_for_capability(Some("7.5")), "cu128");
        assert_eq!(torch_for_capability(Some("6.1\n")), "cpu");
        assert_eq!(torch_for_capability(Some("6.1\n8.9\n")), "cu128");
        assert_eq!(torch_for_capability(Some("garbage")), "cpu");
        assert_eq!(torch_for_capability(None), "cpu");
    }

    #[test]
    fn development_and_installed_data_are_apart() {
        assert!(data_home(true).ends_with("Cover_Maker.dev"));
        assert!(data_home(false).ends_with("Cover_Maker"));
        assert!(default_root().ends_with("Cover_Maker/runtime"));
    }

    #[test]
    fn disk_plan_needs_room_plus_margin() {
        let mut plan = DiskPlan {
            torch: "cpu".into(),
            download_bytes: 1,
            disk_bytes: 2 * SPACE_MARGIN,
            needed_bytes: SPACE_MARGIN,
            free_bytes: Some(2 * SPACE_MARGIN),
            folder: String::new(),
        };
        assert!(plan.fits());
        plan.free_bytes = Some(2 * SPACE_MARGIN - 1);
        assert!(!plan.fits());
        plan.free_bytes = None;
        assert!(plan.fits());
    }

    #[test]
    fn reads_free_space_and_folder_sizes() {
        let dir = std::env::temp_dir().join(format!("cm-size-{}", std::process::id()));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(dir.join("sub")).unwrap();
        fs::write(dir.join("a.bin"), [0u8; 10]).unwrap();
        fs::write(dir.join("sub").join("b.bin"), [0u8; 5]).unwrap();
        assert_eq!(folder_bytes(&dir), 15);
        assert_eq!(folder_bytes(&dir.join("missing")), 0);
        assert!(free_bytes(&dir.join("not").join("yet")).unwrap() > 0);
        fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn hashes_like_sha256sum() {
        assert_eq!(
            sha256_hex(b"abc"),
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        );
    }

    #[test]
    fn extracts_only_bin_files() {
        let mut buffer = std::io::Cursor::new(Vec::new());
        {
            let mut zip = zip::ZipWriter::new(&mut buffer);
            let options = zip::write::SimpleFileOptions::default();
            for (name, body) in [
                ("ffmpeg-x/bin/ffmpeg.exe", "exe"),
                ("ffmpeg-x/bin/avcodec.dll", "dll"),
                ("ffmpeg-x/doc/readme.txt", "doc"),
                ("ffmpeg-x/LICENSE.txt", "lgpl"),
                ("deno.exe", "deno"),
            ] {
                zip.start_file(name, options).unwrap();
                zip.write_all(body.as_bytes()).unwrap();
            }
            zip.finish().unwrap();
        }
        let names_in = |dir: &Path| {
            let mut names: Vec<_> = fs::read_dir(dir)
                .unwrap()
                .map(|e| e.unwrap().file_name().into_string().unwrap())
                .collect();
            names.sort();
            names
        };
        let target = std::env::temp_dir().join(format!("cm-extract-{}", std::process::id()));
        let _ = fs::remove_dir_all(&target);
        extract_bin(buffer.get_ref(), &target.join("bin")).unwrap();
        assert_eq!(
            names_in(&target.join("bin")),
            ["avcodec.dll", "deno.exe", "ffmpeg.exe"]
        );
        let licences = target.join("licenses");
        assert_eq!(extract_licences(buffer.get_ref(), &licences).unwrap(), 1);
        assert_eq!(names_in(&licences), ["LICENSE.txt"]);
        fs::remove_dir_all(&target).unwrap();
    }

    #[test]
    fn reads_the_downloads_of_one_platform() {
        let tool = |name: &str| {
            format!(
                r#"{{"version": "1", "file": "{name}.zip", "urls": ["https://x/{name}.zip"], "sha256": "00"}}"#
            )
        };
        let text = format!(
            r#"{{"windows-x64": {{"uv": {uv}, "ffmpeg": {ffmpeg}, "deno": {deno}}},
                "macos-arm64": {{"uv": {uv}, "ffmpeg": null, "deno": {deno}}}}}"#,
            uv = tool("uv"),
            ffmpeg = tool("ffmpeg"),
            deno = tool("deno"),
        );
        let names = |deps: &Deps| deps.tools().iter().map(|(n, _)| *n).collect::<Vec<_>>();
        let windows = parse_deps(&text, "windows-x64").unwrap();
        assert_eq!(names(&windows), ["ffmpeg", "deno"]);
        let macos = parse_deps(&text, "macos-arm64").unwrap();
        assert_eq!(names(&macos), ["deno"]);
        assert!(parse_deps(&text, "linux-x64").is_err());
    }

    #[test]
    fn bundled_deps_cover_this_platform() {
        let text = include_str!("../resources/runtime/deps.json");
        let deps = parse_deps(text, platform::DEPS_KEY).unwrap();
        assert!(deps.tools().iter().all(|(_, d)| d.sha256.len() == 64));
        assert!(deps.ffmpeg.is_some());
    }

    #[test]
    fn torch_build_is_one_this_platform_has() {
        assert!(platform::TORCH_BUILDS.contains(&torch_build().as_str()));
    }

    #[test]
    fn state_round_trips() {
        let state = InstallState {
            core: Some("1.0.0".into()),
            separation: None,
            torch: Some("cpu".into()),
        };
        let text = serde_json::to_string(&state).unwrap();
        assert_eq!(parse_state(&text), state);
        assert_eq!(parse_state(&format!("\u{feff}{text}")), state);
        assert_eq!(parse_state("not json"), InstallState::default());
    }
}

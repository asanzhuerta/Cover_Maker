//! First-run bootstrap of the engine runtime (ADR-006).
//!
//! Release builds run the engine from a virtual environment in
//! `%LOCALAPPDATA%\Cover_Maker\runtime`, created with the bundled `uv.exe`
//! from the bundled engine wheel and `pylock.*.toml` lock files:
//!
//! - Phase A (core) blocks the engine start: Python 3.12, the venv with the
//!   engine and its core dependencies, ffmpeg and deno.
//! - Phase B (separation) runs in the background once the engine is up:
//!   PyTorch (CUDA cu128 when the GPU supports it, CPU otherwise) and the
//!   separation extra. Downloads stay in the uv cache, so a retry resumes.
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

#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;
/// Lowest compute capability supported by the cu128 PyTorch wheels.
const MIN_CUDA_CAPABILITY: f32 = 7.5;

/// Where the bundled files are and where the runtime goes.
#[derive(Clone, Debug)]
pub struct Layout {
    /// Bundled files (`bundle\` in the install folder): `uv.exe`, the
    /// wheel, `pylock.*.toml` and `deps.json`.
    pub bundle: PathBuf,
    /// `%LOCALAPPDATA%\Cover_Maker\runtime`.
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
        self.venv().join("Scripts").join("cover-maker.exe")
    }

    fn uv(&self) -> PathBuf {
        self.bundle.join("uv.exe")
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

    /// `PATH` for the engine: the runtime tools (ffmpeg, deno) first.
    pub fn path_env(&self) -> std::ffi::OsString {
        let mut paths = vec![self.bin()];
        if let Some(current) = std::env::var_os("PATH") {
            paths.extend(std::env::split_paths(&current));
        }
        std::env::join_paths(paths).unwrap_or_default()
    }
}

/// Default runtime folder, next to the engine data (`paths.py`).
pub fn default_root() -> PathBuf {
    let base = std::env::var_os("LOCALAPPDATA")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("."));
    base.join("Cover_Maker").join("runtime")
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
}

impl BootstrapStatus {
    pub fn development() -> Self {
        Self {
            mode: "development",
            core: PhaseStatus::done(),
            separation: PhaseStatus::done(),
            torch: None,
        }
    }

    pub fn runtime() -> Self {
        Self {
            mode: "runtime",
            core: PhaseStatus::pending(),
            separation: PhaseStatus::pending(),
            torch: None,
        }
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
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(CREATE_NO_WINDOW);
    }
    command
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

#[derive(Debug, Deserialize)]
struct Deps {
    ffmpeg: Download,
    deno: Download,
}

fn load_deps(layout: &Layout) -> Result<Deps, String> {
    let text = fs::read_to_string(layout.bundle.join("deps.json"))
        .map_err(|e| format!("cannot read deps.json: {e}"))?;
    serde_json::from_str(&text).map_err(|e| format!("invalid deps.json: {e}"))
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
        let mut file = fs::File::create(target.join(name)).map_err(|e| e.to_string())?;
        std::io::copy(&mut entry, &mut file).map_err(|e| e.to_string())?;
        file.flush().map_err(|e| e.to_string())?;
    }
    Ok(())
}

/// Install a pinned tool into `bin/` unless that exact build is there.
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
    if current && layout.engine_exe().exists() {
        install_tool(layout, "ffmpeg", &deps.ffmpeg, report)?;
        return install_tool(layout, "deno", &deps.deno, report);
    }
    fs::create_dir_all(&layout.root).map_err(|e| format!("cannot create runtime folder: {e}"))?;
    let venv = layout.venv();
    let total = 5;

    report.step(1, total, "python");
    uv(layout, &[os("python"), os("install"), os("3.12")], report)?;

    report.step(2, total, "venv");
    if !venv.join("Scripts").join("python.exe").exists() {
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

    report.step(4, total, "ffmpeg");
    install_tool(layout, "ffmpeg", &deps.ffmpeg, report)?;
    report.step(5, total, "deno");
    install_tool(layout, "deno", &deps.deno, report)?;

    installed.core = Some(layout.app_version.clone());
    if profile != "core" {
        installed.separation = Some(layout.app_version.clone());
    } else {
        installed.separation = None;
    }
    save_state(layout, &installed)
}

/// PyTorch build for this machine: `COVER_MAKER_TORCH` overrides detection.
pub fn torch_build() -> String {
    if let Ok(forced) = std::env::var("COVER_MAKER_TORCH")
        && (forced == "cpu" || forced == "cu128")
    {
        return forced;
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
    let python = layout.venv().join("Scripts").join("python.exe");
    let mut command = Command::new(python);
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
            os("yt-dlp[default]"),
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
                ("deno.exe", "deno"),
            ] {
                zip.start_file(name, options).unwrap();
                zip.write_all(body.as_bytes()).unwrap();
            }
            zip.finish().unwrap();
        }
        let target = std::env::temp_dir().join(format!("cm-extract-{}", std::process::id()));
        let _ = fs::remove_dir_all(&target);
        extract_bin(buffer.get_ref(), &target).unwrap();
        let mut names: Vec<_> = fs::read_dir(&target)
            .unwrap()
            .map(|e| e.unwrap().file_name().into_string().unwrap())
            .collect();
        names.sort();
        assert_eq!(names, ["avcodec.dll", "deno.exe", "ffmpeg.exe"]);
        fs::remove_dir_all(&target).unwrap();
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

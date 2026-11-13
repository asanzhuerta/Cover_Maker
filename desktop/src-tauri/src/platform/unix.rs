//! macOS (and other Unix systems, which are not supported targets): a process
//! group for the engine's process tree, `~/Library/Application Support` and
//! free space through `statvfs`.

use std::path::{Path, PathBuf};
use std::process::{Child, Command};

/// Kills the engine process tree.
///
/// Unix has no Job Objects. The engine starts as the leader of a new process
/// group, which its children (separation worker, ffmpeg, yt-dlp) join, and the
/// whole group gets `SIGKILL` when the engine is stopped or this guard is
/// dropped. If the shell itself dies without cleaning up (crash or `kill -9`),
/// the engine notices through `COVER_MAKER_PARENT_PID`, stops its children
/// and exits (`api/server.py`).
pub struct ProcessTree {
    group: Option<libc::pid_t>,
}

impl ProcessTree {
    pub fn new() -> Result<Self, String> {
        Ok(Self { group: None })
    }

    /// Start the process as the leader of a new process group.
    pub fn prepare(&self, command: &mut Command) {
        use std::os::unix::process::CommandExt;
        command.process_group(0);
    }

    pub fn adopt(&mut self, child: &Child) -> Result<(), String> {
        let group = libc::pid_t::try_from(child.id())
            .map_err(|_| format!("unexpected engine process id {}", child.id()))?;
        self.group = Some(group);
        Ok(())
    }

    /// `SIGKILL` to every process left in the engine's group.
    pub fn terminate(&mut self) {
        if let Some(group) = self.group.take() {
            // SAFETY: plain system call; a group that is already gone only
            // makes it return ESRCH. The group id cannot be reused while any
            // of its processes is alive.
            unsafe {
                libc::killpg(group, libc::SIGKILL);
            }
        }
    }
}

impl Drop for ProcessTree {
    fn drop(&mut self) {
        self.terminate();
    }
}

/// Nothing to do: console programs open no window on Unix.
pub fn hide_window(command: &mut Command) -> &mut Command {
    command
}

fn home() -> PathBuf {
    std::env::var_os("HOME")
        .filter(|v| !v.is_empty())
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("."))
}

/// `~/Library/Application Support` on macOS; `$XDG_DATA_HOME` (or
/// `~/.local/share`) elsewhere.
pub fn local_data_dir() -> PathBuf {
    if cfg!(target_os = "macos") {
        return home().join("Library").join("Application Support");
    }
    std::env::var_os("XDG_DATA_HOME")
        .filter(|v| !v.is_empty())
        .map(PathBuf::from)
        .unwrap_or_else(|| home().join(".local").join("share"))
}

/// Free bytes for unprivileged users on the volume of an existing `path`.
// The field widths of `statvfs` differ between Unix systems.
#[allow(clippy::unnecessary_cast)]
pub fn free_bytes(path: &Path) -> Option<u64> {
    use std::os::unix::ffi::OsStrExt;
    let path = std::ffi::CString::new(path.as_os_str().as_bytes()).ok()?;
    // SAFETY: an all-zero `statvfs` is a valid value for the call to fill.
    let mut stat: libc::statvfs = unsafe { std::mem::zeroed() };
    // SAFETY: `path` is NUL-terminated and `stat` is writable; both outlive the call.
    if unsafe { libc::statvfs(path.as_ptr(), &mut stat) } != 0 {
        return None;
    }
    Some(stat.f_bavail as u64 * stat.f_frsize as u64)
}

/// Mark an extracted tool (ffmpeg, deno) as executable.
pub fn make_executable(path: &Path) -> std::io::Result<()> {
    use std::os::unix::fs::PermissionsExt;
    std::fs::set_permissions(path, std::fs::Permissions::from_mode(0o755))
}

/// Folders searched after the runtime's own `bin/` and the inherited `PATH`.
///
/// An app started from Finder inherits only `/usr/bin:/bin:/usr/sbin:/sbin`;
/// Homebrew's folders let the engine find a user-installed ffmpeg while the
/// macOS runtime installs none (ADR-013).
pub fn fallback_tool_dirs() -> Vec<PathBuf> {
    if cfg!(target_os = "macos") {
        vec![
            PathBuf::from("/opt/homebrew/bin"),
            PathBuf::from("/usr/local/bin"),
        ]
    } else {
        Vec::new()
    }
}

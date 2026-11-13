//! What differs between desktop platforms (ADR-013): how the engine's process
//! tree is stopped, console windows, the per-user data folder, free disk space
//! and file names. Windows is the reference platform; macOS on Apple Silicon is
//! experimental. Every function has the same signature on each platform.

// `win`, not `windows`, which would shadow the `windows` crate.
#[cfg(windows)]
mod win;
#[cfg(windows)]
pub use win::*;

#[cfg(unix)]
mod unix;
#[cfg(unix)]
pub use unix::*;

/// Folder of a virtual environment's executables.
pub const VENV_BIN: &str = if cfg!(windows) { "Scripts" } else { "bin" };

/// `name` with the platform's executable suffix: `uv.exe` on Windows, `uv`
/// elsewhere.
pub fn exe(name: &str) -> String {
    format!("{name}{}", std::env::consts::EXE_SUFFIX)
}

/// Install profiles of the separation runtime (the `pylock.<profile>.toml`
/// lock files) that this platform can use, the default first: PyTorch for
/// the CPU or CUDA on Windows, PyTorch with Metal (MPS) on macOS, which also
/// runs on the CPU.
pub const TORCH_BUILDS: &[&str] = if cfg!(target_os = "macos") {
    &["mps"]
} else {
    &["cpu", "cu128"]
};

/// Key of this platform's pinned downloads in `deps.json`.
pub const DEPS_KEY: &str = if cfg!(target_os = "macos") {
    "macos-arm64"
} else {
    "windows-x64"
};

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn names_follow_the_platform() {
        if cfg!(windows) {
            assert_eq!(exe("uv"), "uv.exe");
            assert_eq!(VENV_BIN, "Scripts");
            assert_eq!(DEPS_KEY, "windows-x64");
        } else {
            assert_eq!(exe("uv"), "uv");
            assert_eq!(VENV_BIN, "bin");
        }
        assert!(!TORCH_BUILDS.is_empty());
    }

    #[test]
    fn reads_free_space_of_an_existing_folder() {
        assert!(free_bytes(&std::env::temp_dir()).unwrap() > 0);
    }

    #[test]
    fn data_folder_is_per_user() {
        let dir = local_data_dir();
        if cfg!(target_os = "macos") {
            assert!(dir.ends_with("Library/Application Support"));
        }
        assert!(!dir.as_os_str().is_empty());
    }
}

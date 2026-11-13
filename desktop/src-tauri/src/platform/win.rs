//! Windows: a Job Object for the engine's process tree, hidden console
//! windows, `%LOCALAPPDATA%` and free space through the Win32 API.

use std::os::windows::io::AsRawHandle;
use std::path::{Path, PathBuf};
use std::process::{Child, Command};

use windows::Win32::Foundation::{CloseHandle, HANDLE};
use windows::Win32::System::JobObjects::{
    AssignProcessToJobObject, CreateJobObjectW, JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION, JobObjectExtendedLimitInformation,
    SetInformationJobObject,
};

const CREATE_NO_WINDOW: u32 = 0x0800_0000;

/// Kills the engine process tree when the shell exits.
///
/// The job is created with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`: when the last
/// handle to it is closed (normal exit, crash or `taskkill /F` of the shell),
/// Windows terminates every process assigned to the job and all of their
/// descendants created afterwards.
pub struct ProcessTree(HANDLE);

// The handle is only used to keep the job alive and is closed once on drop.
unsafe impl Send for ProcessTree {}
unsafe impl Sync for ProcessTree {}

impl ProcessTree {
    pub fn new() -> Result<Self, String> {
        Self::create_job().map_err(|e| format!("cannot create job object: {e}"))
    }

    fn create_job() -> windows::core::Result<Self> {
        unsafe {
            let job = CreateJobObjectW(None, None)?;
            let mut info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION::default();
            info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
            SetInformationJobObject(
                job,
                JobObjectExtendedLimitInformation,
                &info as *const _ as *const core::ffi::c_void,
                std::mem::size_of::<JOBOBJECT_EXTENDED_LIMIT_INFORMATION>() as u32,
            )?;
            Ok(Self(job))
        }
    }

    /// Nothing to do before the start: the process joins the job afterwards.
    pub fn prepare(&self, _command: &mut Command) {}

    pub fn adopt(&mut self, child: &Child) -> Result<(), String> {
        unsafe { AssignProcessToJobObject(self.0, HANDLE(child.as_raw_handle())) }
            .map_err(|e| format!("cannot assign engine to job object: {e}"))
    }

    /// Nothing to do: the job kills the tree when its handle closes (on drop
    /// or when the shell exits).
    pub fn terminate(&mut self) {}
}

impl Drop for ProcessTree {
    fn drop(&mut self) {
        unsafe {
            let _ = CloseHandle(self.0);
        }
    }
}

/// Start console programs without opening a console window.
pub fn hide_window(command: &mut Command) -> &mut Command {
    use std::os::windows::process::CommandExt;
    command.creation_flags(CREATE_NO_WINDOW)
}

/// `%LOCALAPPDATA%`.
pub fn local_data_dir() -> PathBuf {
    std::env::var_os("LOCALAPPDATA")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("."))
}

/// Free bytes on the volume of an existing `path`.
pub fn free_bytes(path: &Path) -> Option<u64> {
    use std::os::windows::ffi::OsStrExt;
    use windows::Win32::Storage::FileSystem::GetDiskFreeSpaceExW;
    use windows::core::PCWSTR;
    let wide: Vec<u16> = path
        .as_os_str()
        .encode_wide()
        .chain(std::iter::once(0))
        .collect();
    let mut free = 0u64;
    // SAFETY: `wide` is a NUL-terminated path that outlives the call.
    unsafe { GetDiskFreeSpaceExW(PCWSTR(wide.as_ptr()), Some(&mut free), None, None) }.ok()?;
    Some(free)
}

/// Nothing to do: Windows has no executable bit.
pub fn make_executable(_path: &Path) -> std::io::Result<()> {
    Ok(())
}

/// Folders searched for tools the runtime does not install: none.
pub fn fallback_tool_dirs() -> Vec<PathBuf> {
    Vec::new()
}

//! Windows Job Object that kills the engine process tree when the shell exits.
//!
//! The job is created with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`: when the last
//! handle to it is closed (normal exit, crash or `taskkill /F` of the shell),
//! Windows terminates every process assigned to the job and all of their
//! descendants created afterwards.

#[cfg(windows)]
mod imp {
    use std::os::windows::io::AsRawHandle;
    use std::process::Child;

    use windows::Win32::Foundation::{CloseHandle, HANDLE};
    use windows::Win32::System::JobObjects::{
        AssignProcessToJobObject, CreateJobObjectW, JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
        JOBOBJECT_EXTENDED_LIMIT_INFORMATION, JobObjectExtendedLimitInformation,
        SetInformationJobObject,
    };

    pub struct KillOnCloseJob(HANDLE);

    // The handle is only used to keep the job alive and is closed once on drop.
    unsafe impl Send for KillOnCloseJob {}
    unsafe impl Sync for KillOnCloseJob {}

    impl KillOnCloseJob {
        pub fn new() -> windows::core::Result<Self> {
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

        pub fn assign(&self, child: &Child) -> windows::core::Result<()> {
            unsafe { AssignProcessToJobObject(self.0, HANDLE(child.as_raw_handle())) }
        }
    }

    impl Drop for KillOnCloseJob {
        fn drop(&mut self) {
            unsafe {
                let _ = CloseHandle(self.0);
            }
        }
    }
}

#[cfg(not(windows))]
mod imp {
    use std::process::Child;

    /// No-op on other platforms (Windows is the only supported target).
    pub struct KillOnCloseJob;

    impl KillOnCloseJob {
        pub fn new() -> std::io::Result<Self> {
            Ok(Self)
        }

        pub fn assign(&self, _child: &Child) -> std::io::Result<()> {
            Ok(())
        }
    }
}

pub use imp::KillOnCloseJob;

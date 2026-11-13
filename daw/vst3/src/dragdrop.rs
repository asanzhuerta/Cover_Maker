//! Dragging stem files out of the plugin window into the host's tracks.
//!
//! Windows hosts accept files dropped from Explorer (`CF_HDROP`). The shell
//! builds that data object for us from the files' item IDs; we only provide the
//! drop source that ends the drag when the mouse button is released.

use std::path::{Path, PathBuf};

#[cfg(windows)]
mod imp {
    use std::os::windows::ffi::OsStrExt;
    use std::path::PathBuf;

    use windows::core::{implement, HRESULT, PCWSTR};
    use windows::Win32::Foundation::{
        BOOL, DRAGDROP_S_CANCEL, DRAGDROP_S_DROP, DRAGDROP_S_USEDEFAULTCURSORS, S_OK,
    };
    use windows::Win32::System::Com::{CoTaskMemFree, IDataObject};
    use windows::Win32::System::Ole::{
        DoDragDrop, IDropSource, IDropSource_Impl, OleInitialize, DROPEFFECT, DROPEFFECT_COPY,
    };
    use windows::Win32::System::SystemServices::{MK_LBUTTON, MODIFIERKEYS_FLAGS};
    use windows::Win32::UI::Shell::Common::ITEMIDLIST;
    use windows::Win32::UI::Shell::{
        BHID_DataObject, IShellItemArray, SHCreateShellItemArrayFromIDLists, SHParseDisplayName,
    };

    #[implement(IDropSource)]
    struct DropSource;

    impl IDropSource_Impl for DropSource_Impl {
        fn QueryContinueDrag(&self, escape: BOOL, keys: MODIFIERKEYS_FLAGS) -> HRESULT {
            if escape.as_bool() {
                DRAGDROP_S_CANCEL
            } else if (keys & MK_LBUTTON).0 == 0 {
                DRAGDROP_S_DROP
            } else {
                S_OK
            }
        }

        fn GiveFeedback(&self, _effect: DROPEFFECT) -> HRESULT {
            DRAGDROP_S_USEDEFAULTCURSORS
        }
    }

    fn wide(path: &std::path::Path) -> Vec<u16> {
        path.as_os_str().encode_wide().chain(Some(0)).collect()
    }

    pub fn drag(files: &[PathBuf]) -> Result<(), String> {
        unsafe {
            // S_FALSE when the host already initialised OLE on this thread.
            OleInitialize(None).map_err(|e| format!("OLE unavailable: {e}"))?;
            let mut pidls: Vec<*mut ITEMIDLIST> = Vec::with_capacity(files.len());
            let result = (|| {
                for file in files {
                    let name = wide(file);
                    let mut pidl = std::ptr::null_mut();
                    SHParseDisplayName(PCWSTR(name.as_ptr()), None, &mut pidl, 0, None)
                        .map_err(|e| format!("{}: {e}", file.display()))?;
                    pidls.push(pidl);
                }
                let list: Vec<*const ITEMIDLIST> = pidls.iter().map(|p| *p as *const _).collect();
                let array: IShellItemArray =
                    SHCreateShellItemArrayFromIDLists(&list).map_err(|e| e.to_string())?;
                let data: IDataObject = array
                    .BindToHandler(None, &BHID_DataObject)
                    .map_err(|e| e.to_string())?;
                let source: IDropSource = DropSource.into();
                let mut effect = DROPEFFECT::default();
                let hr = DoDragDrop(&data, &source, DROPEFFECT_COPY, &mut effect);
                if hr.is_err() {
                    return Err(hr.message());
                }
                Ok(())
            })();
            for pidl in pidls {
                CoTaskMemFree(Some(pidl as *const _));
            }
            result
        }
    }
}

/// Starts a modal drag of `files`; returns when they are dropped or the drag is cancelled.
pub fn drag_files(files: &[PathBuf]) -> Result<(), String> {
    let existing: Vec<PathBuf> = files.iter().filter(|f| f.is_file()).cloned().collect();
    if existing.is_empty() {
        return Err("The stem files are missing.".into());
    }
    #[cfg(windows)]
    {
        imp::drag(&existing)
    }
    #[cfg(not(windows))]
    {
        Err("Dragging files is only supported on Windows.".into())
    }
}

/// Opens Explorer (Finder on macOS) with the file selected.
pub fn show_in_folder(file: &Path) {
    #[cfg(windows)]
    {
        let root = std::env::var_os("SYSTEMROOT").unwrap_or_else(|| "C:\\Windows".into());
        let explorer = PathBuf::from(root).join("explorer.exe");
        let _ = std::process::Command::new(explorer)
            .arg(format!("/select,{}", file.display()))
            .spawn();
    }
    #[cfg(target_os = "macos")]
    {
        let _ = std::process::Command::new("/usr/bin/open")
            .arg("-R")
            .arg(file)
            .spawn();
    }
    #[cfg(not(any(windows, target_os = "macos")))]
    let _ = file;
}

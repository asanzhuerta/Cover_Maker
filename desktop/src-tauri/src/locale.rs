//! Default UI language chosen in the installer.
//!
//! The NSIS hook stores the installer's language id (`$LANGUAGE`) in
//! `HKCU\Software\Cover_Maker\Language`; the UI asks for it on first start.

/// UI locale for a Windows language id: Spanish for any Spanish variant.
pub fn locale_for_language_id(id: u32) -> &'static str {
    // The low 10 bits are the primary language; 0x0a is Spanish.
    if id & 0x3ff == 0x0a { "es" } else { "en" }
}

#[cfg(windows)]
fn installer_language_id() -> Option<u32> {
    use windows::Win32::System::Registry::{HKEY_CURRENT_USER, RRF_RT_REG_SZ, RegGetValueW};
    use windows::core::w;

    let mut buffer = [0u16; 16];
    let mut size = std::mem::size_of_val(&buffer) as u32;
    // SAFETY: the buffer and its size in bytes describe valid, writable memory.
    let status = unsafe {
        RegGetValueW(
            HKEY_CURRENT_USER,
            w!("Software\\Cover_Maker"),
            w!("Language"),
            RRF_RT_REG_SZ,
            None,
            Some(buffer.as_mut_ptr().cast()),
            Some(&mut size),
        )
    };
    if status.is_err() {
        return None;
    }
    let chars = (size as usize / 2).min(buffer.len());
    String::from_utf16_lossy(&buffer[..chars])
        .trim_end_matches('\0')
        .trim()
        .parse()
        .ok()
}

#[cfg(not(windows))]
fn installer_language_id() -> Option<u32> {
    None
}

/// Locale picked in the installer, if the app was installed with one.
pub fn installer_locale() -> Option<&'static str> {
    installer_language_id().map(locale_for_language_id)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn maps_windows_language_ids() {
        assert_eq!(locale_for_language_id(1034), "es"); // Spanish, traditional sort
        assert_eq!(locale_for_language_id(3082), "es"); // Spanish, modern sort
        assert_eq!(locale_for_language_id(2058), "es"); // Spanish (Mexico)
        assert_eq!(locale_for_language_id(1033), "en");
        assert_eq!(locale_for_language_id(1036), "en"); // French: not translated
    }
}

//! Cover_Maker desktop shell. Business logic lives in the Python engine; the
//! shell only handles OS integration (windows, dialogs, engine lifecycle).

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .run(tauri::generate_context!())
        .expect("error while running the Cover_Maker shell");
}

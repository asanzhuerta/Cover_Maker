//! Cover_Maker desktop shell. Business logic lives in the Python engine; the
//! shell only handles OS integration (windows, dialogs, engine lifecycle).

mod engine;
mod jobobject;

use engine::{EngineInfo, EngineState};
use tauri::{Manager, RunEvent, State};

/// Returns how to reach the engine, starting it on first use.
#[tauri::command]
async fn engine_info(state: State<'_, EngineState>) -> Result<EngineInfo, String> {
    let mut guard = state.0.lock().map_err(|_| "engine state poisoned")?;
    if guard.is_none() {
        *guard = Some(engine::start()?);
    }
    Ok(guard.as_ref().expect("engine just started").info.clone())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(EngineState::default())
        .invoke_handler(tauri::generate_handler![engine_info])
        .build(tauri::generate_context!())
        .expect("error while building the Cover_Maker shell")
        .run(|app, event| {
            if let RunEvent::Exit = event
                && let Ok(mut guard) = app.state::<EngineState>().0.lock()
                && let Some(engine) = guard.as_mut()
            {
                engine.kill();
            }
        });
}

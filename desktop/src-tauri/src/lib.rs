//! Cover_Maker desktop shell. Business logic lives in the Python engine; the
//! shell only handles OS integration (windows, dialogs, engine lifecycle and
//! the first-run bootstrap of the engine runtime).

mod engine;
mod jobobject;
mod locale;
mod runtime;

use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};

use engine::{EngineInfo, EngineState};
use runtime::{BootstrapState, BootstrapStatus, Layout, YtDlpVersions};
use tauri::{AppHandle, Emitter, Manager, RunEvent, State};

/// The runtime layout in release builds; `None` runs the repository engine.
struct Runtime {
    layout: Option<Layout>,
    /// Set while the bootstrap thread runs.
    busy: Arc<AtomicBool>,
}

fn notifier(app: &AppHandle) -> impl Fn(&BootstrapStatus) + Send + Sync + 'static {
    let app = app.clone();
    move |status: &BootstrapStatus| {
        let _ = app.emit("bootstrap", status);
    }
}

/// Run phase A, then phase B, on a background thread (once at a time).
fn spawn_bootstrap(app: &AppHandle) {
    let runtime = app.state::<Runtime>();
    let Some(layout) = runtime.layout.clone() else {
        return;
    };
    if runtime.busy.swap(true, Ordering::SeqCst) {
        return;
    }
    let busy = runtime.busy.clone();
    let app = app.clone();
    std::thread::spawn(move || {
        let state = app.state::<BootstrapState>();
        let notify = notifier(&app);
        if runtime::ensure_core(&layout, &state, &notify).is_ok() {
            let _ = runtime::ensure_separation(&layout, &state, &notify);
        }
        busy.store(false, Ordering::SeqCst);
    });
}

/// Returns how to reach the engine, starting it on first use.
#[tauri::command]
async fn engine_info(
    state: State<'_, EngineState>,
    runtime: State<'_, Runtime>,
    bootstrap: State<'_, BootstrapState>,
) -> Result<EngineInfo, String> {
    if runtime.layout.is_some() {
        let status = bootstrap.0.lock().map_err(|_| "bootstrap state poisoned")?;
        if status.core.state != "done" {
            return Err("the engine runtime is still being installed".into());
        }
    }
    let mut guard = state.0.lock().map_err(|_| "engine state poisoned")?;
    if guard.is_none() {
        *guard = Some(engine::start(runtime.layout.as_ref())?);
    }
    Ok(guard.as_ref().expect("engine just started").info.clone())
}

#[tauri::command]
fn bootstrap_status(bootstrap: State<'_, BootstrapState>) -> Result<BootstrapStatus, String> {
    Ok(bootstrap
        .0
        .lock()
        .map_err(|_| "bootstrap state poisoned")?
        .clone())
}

/// Start the bootstrap: on a first run after the user's OK, or again after a
/// failure (downloads resume from the cache).
#[tauri::command]
fn bootstrap_retry(app: AppHandle) {
    spawn_bootstrap(&app);
}

/// Stop the engine; the UI reconnects and `engine_info` starts a fresh one.
#[tauri::command]
fn restart_engine(state: State<'_, EngineState>) -> Result<(), String> {
    let mut guard = state.0.lock().map_err(|_| "engine state poisoned")?;
    if let Some(mut engine) = guard.take() {
        engine.kill();
    }
    Ok(())
}

fn installed_layout(runtime: &Runtime) -> Result<Layout, String> {
    runtime.layout.clone().ok_or_else(|| {
        "Development build: update yt-dlp with `uv lock --upgrade-package yt-dlp` in engine/."
            .into()
    })
}

#[tauri::command]
async fn check_ytdlp(runtime: State<'_, Runtime>) -> Result<YtDlpVersions, String> {
    let layout = installed_layout(&runtime)?;
    tauri::async_runtime::spawn_blocking(move || runtime::check_ytdlp(&layout))
        .await
        .map_err(|e| e.to_string())?
}

/// Upgrade yt-dlp and restart the engine so it loads the new version.
#[tauri::command]
async fn update_ytdlp(app: AppHandle, runtime: State<'_, Runtime>) -> Result<String, String> {
    let layout = installed_layout(&runtime)?;
    let worker = app.clone();
    let version = tauri::async_runtime::spawn_blocking(move || {
        let state = worker.state::<BootstrapState>();
        runtime::update_ytdlp(&layout, &state, &notifier(&worker))
    })
    .await
    .map_err(|e| e.to_string())??;
    restart_engine(app.state::<EngineState>())?;
    Ok(version)
}

/// Open one of the engine's data folders in Explorer. Only these fixed
/// sub-folders of the data home (`paths.py`) can be opened.
#[tauri::command]
fn open_data_folder(name: String) -> Result<(), String> {
    if !["tmp", "models", "library", "logs", "runtime"].contains(&name.as_str()) {
        return Err(format!("unknown folder {name}"));
    }
    let home = match std::env::var_os("COVER_MAKER_HOME").filter(|v| !v.is_empty()) {
        Some(dir) => std::path::PathBuf::from(dir),
        None => runtime::data_home(engine::development()),
    };
    let folder = home.join(&name);
    std::fs::create_dir_all(&folder).map_err(|e| format!("cannot create {name}: {e}"))?;
    tauri_plugin_opener::open_path(folder, None::<&str>).map_err(|e| e.to_string())
}

/// Language picked in the installer (`en` or `es`), used as the first default.
#[tauri::command]
fn installer_locale() -> Option<&'static str> {
    locale::installer_locale()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .manage(EngineState::default())
        .setup(|app| {
            let layout = if engine::development() {
                None
            } else {
                Some(Layout {
                    bundle: app.path().resource_dir()?.join("bundle"),
                    root: runtime::default_root(),
                    app_version: app.package_info().version.to_string(),
                })
            };
            // A first run waits on the setup screen, which shows what the
            // runtime downloads and the disk space it needs, until the user
            // starts it (`bootstrap_retry`). Updates and repairs start at once.
            let consent = layout.as_ref().is_some_and(runtime::first_run);
            let status = match &layout {
                Some(layout) if consent => {
                    BootstrapStatus::awaiting_consent(runtime::disk_plan(
                        layout,
                        &runtime::torch_build(),
                    ))
                }
                Some(_) => BootstrapStatus::runtime(),
                None => BootstrapStatus::development(),
            };
            app.manage(BootstrapState(std::sync::Mutex::new(status)));
            app.manage(Runtime {
                layout,
                busy: Arc::new(AtomicBool::new(false)),
            });
            if !consent {
                spawn_bootstrap(app.handle());
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            engine_info,
            bootstrap_status,
            bootstrap_retry,
            restart_engine,
            check_ytdlp,
            update_ytdlp,
            open_data_folder,
            installer_locale
        ])
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

//! Cover_Maker VST3 plugin.
//!
//! A client of the Cover_Maker engine running on the same computer (ADR-008):
//! give it a file or a video link, choose the stems, run the separation, then
//! preview each stem through the plugin's output and drag the files into
//! tracks. VST3 plugins cannot create tracks themselves.
//!
//! Licensed under GPL-3.0-or-later because NIH-plug's VST3 bindings are GPLv3;
//! the rest of Cover_Maker is MIT.

// nih_export_vst3! expands with a trailing semicolon that newer rustc warns about.
#![allow(semicolon_in_expressions_from_non_local_macros)]

use std::path::PathBuf;
use std::sync::{Arc, Mutex};
use std::time::Duration;

use nih_plug::prelude::*;
use nih_plug_egui::{create_egui_editor, egui, EguiState};

pub mod dragdrop;
pub mod engine;
pub mod preview;
pub mod theme;

use engine::{Client, JobRequest, STEMS};
use preview::Preview;

/// What the background job thread reports to the editor.
#[derive(Default)]
struct JobState {
    busy: bool,
    status: String,
    stems: Vec<(String, PathBuf)>,
}

#[derive(Default)]
struct Shared {
    job: Mutex<JobState>,
    preview: Mutex<Option<Preview>>,
    playing: Mutex<Option<String>>,
}

/// The editor's form, kept while the window is closed.
struct Form {
    input: String,
    stems: [bool; STEMS.len()],
    rights: bool,
    output_dir: String,
}

impl Default for Form {
    fn default() -> Self {
        let music = std::env::var_os("USERPROFILE")
            .map(|home| PathBuf::from(home).join("Music"))
            .unwrap_or_else(std::env::temp_dir);
        Self {
            input: String::new(),
            stems: [true, true, true, false, false, true],
            rights: false,
            output_dir: music
                .join("Cover_Maker stems")
                .to_string_lossy()
                .into_owned(),
        }
    }
}

impl Form {
    fn wanted(&self) -> Vec<String> {
        STEMS
            .iter()
            .zip(self.stems)
            .filter(|(_, on)| *on)
            .map(|(s, _)| s.to_string())
            .collect()
    }
}

#[derive(Params)]
struct CoverMakerParams {
    #[persist = "editor-state"]
    editor_state: Arc<EguiState>,
    /// Level of the stem preview added to the track's signal.
    #[id = "preview"]
    preview_gain: FloatParam,
}

impl Default for CoverMakerParams {
    fn default() -> Self {
        Self {
            editor_state: EguiState::from_size(460, 520),
            preview_gain: FloatParam::new(
                "Preview level",
                util::db_to_gain(-6.0),
                FloatRange::Skewed {
                    min: util::db_to_gain(-60.0),
                    max: util::db_to_gain(6.0),
                    factor: FloatRange::gain_skew_factor(-60.0, 6.0),
                },
            )
            .with_smoother(SmoothingStyle::Logarithmic(50.0))
            .with_unit(" dB")
            .with_value_to_string(formatters::v2s_f32_gain_to_db(1))
            .with_string_to_value(formatters::s2v_f32_gain_to_db()),
        }
    }
}

pub struct CoverMaker {
    params: Arc<CoverMakerParams>,
    shared: Arc<Shared>,
    sample_rate: f32,
}

impl Default for CoverMaker {
    fn default() -> Self {
        Self {
            params: Arc::new(CoverMakerParams::default()),
            shared: Arc::new(Shared::default()),
            sample_rate: 44_100.0,
        }
    }
}

fn run_job(shared: Arc<Shared>, request: JobRequest) {
    let set = |status: String| {
        if let Ok(mut job) = shared.job.lock() {
            job.status = status;
        }
    };
    let result = (|| -> Result<Vec<(String, PathBuf)>, String> {
        let client = Client::connect()?;
        set("Sent to Cover_Maker…".into());
        let id = client.submit(&request)?;
        loop {
            std::thread::sleep(Duration::from_secs(1));
            let job = client.job(id)?;
            set(job.describe());
            if job.finished() {
                if job.status != "done" {
                    return Err(job.describe());
                }
                return Ok(job.stems(&request.stems));
            }
        }
    })();
    if let Ok(mut job) = shared.job.lock() {
        job.busy = false;
        match result {
            Ok(stems) => {
                job.status = format!("Done: {} stems. Drag them into your tracks.", stems.len());
                job.stems = stems;
            }
            Err(message) => job.status = message,
        }
    }
}

fn start(shared: &Arc<Shared>, form: &Form) {
    let wanted = form.wanted();
    if form.input.trim().is_empty() || wanted.is_empty() {
        if let Ok(mut job) = shared.job.lock() {
            job.status = "Give a file or link and choose at least one stem.".into();
        }
        return;
    }
    let request = JobRequest::new(
        &form.input,
        &wanted,
        std::path::Path::new(&form.output_dir),
        form.rights,
    );
    if let Ok(mut job) = shared.job.lock() {
        job.busy = true;
        job.stems.clear();
        job.status = "Connecting…".into();
    }
    let shared = shared.clone();
    std::thread::spawn(move || run_job(shared, request));
}

fn toggle_preview(shared: &Shared, name: &str, path: &std::path::Path) -> Result<(), String> {
    let mut playing = shared.playing.lock().map_err(|e| e.to_string())?;
    if playing.as_deref() == Some(name) {
        *playing = None;
        *shared.preview.lock().map_err(|e| e.to_string())? = None;
        return Ok(());
    }
    let preview = Preview::load(path)?;
    *shared.preview.lock().map_err(|e| e.to_string())? = Some(preview);
    *playing = Some(name.to_string());
    Ok(())
}

fn editor_ui(ui: &mut egui::Ui, shared: &Arc<Shared>, form: &mut Form) {
    ui.horizontal(|ui| {
        ui.heading("Cover");
        ui.add_space(-ui.spacing().item_spacing.x);
        ui.label(egui::RichText::new("_").heading().color(theme::ACCENT));
        ui.add_space(-ui.spacing().item_spacing.x);
        ui.heading("Maker");
    });
    ui.label(
        egui::RichText::new("the cover musician's studio")
            .small()
            .color(theme::MUTED),
    );
    ui.label("Separate a song with the Cover_Maker app (it must be open).");
    ui.add_space(6.0);

    ui.label("File or video link");
    ui.add(
        egui::TextEdit::singleline(&mut form.input)
            .hint_text("C:\\Music\\song.flac or https://…")
            .desired_width(f32::INFINITY),
    );
    ui.horizontal_wrapped(|ui| {
        for (i, stem) in STEMS.iter().enumerate() {
            ui.checkbox(&mut form.stems[i], *stem);
        }
    });
    ui.checkbox(
        &mut form.rights,
        "I have the rights to this audio (needed for links)",
    );
    ui.label("Save stems in");
    ui.add(egui::TextEdit::singleline(&mut form.output_dir).desired_width(f32::INFINITY));

    let (busy, status, stems) = match shared.job.lock() {
        Ok(job) => (job.busy, job.status.clone(), job.stems.clone()),
        Err(_) => (false, String::new(), Vec::new()),
    };
    ui.add_space(4.0);
    ui.horizontal(|ui| {
        if ui
            .add_enabled(
                !busy,
                egui::Button::new(egui::RichText::new("Separate").color(theme::BG))
                    .fill(theme::ACCENT),
            )
            .clicked()
        {
            start(shared, form);
        }
        if busy {
            ui.spinner();
        }
        ui.label(status);
    });

    if !stems.is_empty() {
        ui.separator();
        ui.label("Drag a stem onto a track, or play it here:");
        let playing = shared.playing.lock().ok().and_then(|p| p.clone());
        let mut error = None;
        for (name, path) in &stems {
            ui.horizontal(|ui| {
                let label = if playing.as_deref() == Some(name.as_str()) {
                    "■"
                } else {
                    "▶"
                };
                if ui.button(label).on_hover_text("Preview").clicked() {
                    if let Err(e) = toggle_preview(shared, name, path) {
                        error = Some(e);
                    }
                }
                let handle = ui
                    .add(egui::Label::new(format!("⠿ {name}")).sense(egui::Sense::drag()))
                    .on_hover_text(path.display().to_string());
                if handle.drag_started() {
                    if let Err(e) = dragdrop::drag_files(std::slice::from_ref(path)) {
                        error = Some(e);
                    }
                }
                if ui.small_button("Show in folder").clicked() {
                    dragdrop::show_in_folder(path);
                }
            });
        }
        let all = ui
            .add(egui::Label::new("⠿ Drag all stems").sense(egui::Sense::drag()))
            .on_hover_text("Some hosts put each file on its own track");
        if all.drag_started() {
            let files: Vec<PathBuf> = stems.iter().map(|(_, p)| p.clone()).collect();
            if let Err(e) = dragdrop::drag_files(&files) {
                error = Some(e);
            }
        }
        if let Some(e) = error {
            if let Ok(mut job) = shared.job.lock() {
                job.status = e;
            }
        }
    }
    ui.add_space(8.0);
    ui.label(
        egui::RichText::new("Only separate audio you have the right to use.")
            .small()
            .color(theme::MUTED),
    );
}

impl Plugin for CoverMaker {
    const NAME: &'static str = "Cover_Maker";
    const VENDOR: &'static str = "Cover_Maker";
    const URL: &'static str = "https://github.com/asanzhuerta/Cover_Maker";
    const EMAIL: &'static str = "";
    const VERSION: &'static str = env!("CARGO_PKG_VERSION");

    const AUDIO_IO_LAYOUTS: &'static [AudioIOLayout] = &[AudioIOLayout {
        main_input_channels: NonZeroU32::new(2),
        main_output_channels: NonZeroU32::new(2),
        ..AudioIOLayout::const_default()
    }];

    type SysExMessage = ();
    type BackgroundTask = ();

    fn params(&self) -> Arc<dyn Params> {
        self.params.clone()
    }

    fn editor(&mut self, _executor: AsyncExecutor<Self>) -> Option<Box<dyn Editor>> {
        let shared = self.shared.clone();
        create_egui_editor(
            self.params.editor_state.clone(),
            Form::default(),
            |ctx, _| theme::apply(ctx),
            move |ctx, _setter, form| {
                // Keep polling the job status while the window is open.
                ctx.request_repaint_after(Duration::from_millis(250));
                egui::CentralPanel::default().show(ctx, |ui| editor_ui(ui, &shared, form));
            },
        )
    }

    fn initialize(
        &mut self,
        _layout: &AudioIOLayout,
        config: &BufferConfig,
        _context: &mut impl InitContext<Self>,
    ) -> bool {
        self.sample_rate = config.sample_rate;
        true
    }

    fn process(
        &mut self,
        buffer: &mut Buffer,
        _aux: &mut AuxiliaryBuffers,
        _context: &mut impl ProcessContext<Self>,
    ) -> ProcessStatus {
        // Never block the audio thread: skip the preview if the editor holds it.
        let Ok(mut guard) = self.shared.preview.try_lock() else {
            return ProcessStatus::Normal;
        };
        let Some(preview) = guard.as_mut() else {
            return ProcessStatus::Normal;
        };
        for mut frame in buffer.iter_samples() {
            let gain = self.params.preview_gain.smoothed.next();
            let (l, r) = preview.next_frame(self.sample_rate, gain);
            let mut channels = frame.iter_mut();
            if let Some(s) = channels.next() {
                *s += l;
            }
            if let Some(s) = channels.next() {
                *s += r;
            }
        }
        ProcessStatus::Normal
    }
}

impl Vst3Plugin for CoverMaker {
    const VST3_CLASS_ID: [u8; 16] = *b"CoverMakerStems1";
    const VST3_SUBCATEGORIES: &'static [Vst3SubCategory] =
        &[Vst3SubCategory::Fx, Vst3SubCategory::Tools];
}

nih_export_vst3!(CoverMaker);

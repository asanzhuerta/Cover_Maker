//! Tape & Console colours for the plugin window (ADR-009), the same tokens as
//! the desktop app's dark theme.

use nih_plug_egui::egui::{self, Color32, CornerRadius, Stroke};

pub const BG: Color32 = Color32::from_rgb(0x0c, 0x0b, 0x0a);
pub const SURFACE: Color32 = Color32::from_rgb(0x15, 0x13, 0x0f);
pub const SURFACE_2: Color32 = Color32::from_rgb(0x1d, 0x1a, 0x16);
pub const SURFACE_3: Color32 = Color32::from_rgb(0x29, 0x25, 0x1f);
pub const FG: Color32 = Color32::from_rgb(0xf1, 0xe9, 0xdc);
pub const MUTED: Color32 = Color32::from_rgb(0xa5, 0x9d, 0x90);
/// Hairline border: the text colour at 10 % over the surface.
pub const BORDER: Color32 = Color32::from_rgb(0x2b, 0x29, 0x25);
pub const ACCENT: Color32 = Color32::from_rgb(0xff, 0x6a, 0x3d);
pub const ACCENT_STRONG: Color32 = Color32::from_rgb(0xe0, 0x4e, 0x22);
pub const LINK: Color32 = Color32::from_rgb(0x5b, 0x7c, 0xff);
pub const WARN: Color32 = Color32::from_rgb(0xff, 0xc0, 0x4d);
pub const DANGER: Color32 = Color32::from_rgb(0xff, 0x4d, 0x4d);

/// Width of borders and outlines.
const HAIRLINE: f32 = 1.0;

/// Apply the colours once, when the editor window opens.
pub fn apply(ctx: &egui::Context) {
    let mut visuals = egui::Visuals::dark();
    visuals.override_text_color = Some(FG);
    visuals.panel_fill = SURFACE;
    visuals.window_fill = SURFACE;
    visuals.window_stroke = Stroke::new(HAIRLINE, BORDER);
    visuals.window_corner_radius = CornerRadius::same(8);
    visuals.extreme_bg_color = BG;
    visuals.faint_bg_color = SURFACE_2;
    visuals.code_bg_color = SURFACE_2;
    visuals.hyperlink_color = LINK;
    visuals.warn_fg_color = WARN;
    visuals.error_fg_color = DANGER;
    visuals.selection.bg_fill = ACCENT_STRONG;
    visuals.selection.stroke = Stroke::new(HAIRLINE, FG);

    let radius = CornerRadius::same(4);
    let widgets = &mut visuals.widgets;
    widgets.noninteractive.bg_fill = SURFACE;
    widgets.noninteractive.weak_bg_fill = SURFACE;
    widgets.noninteractive.bg_stroke = Stroke::new(HAIRLINE, BORDER);
    widgets.noninteractive.fg_stroke = Stroke::new(HAIRLINE, MUTED);
    widgets.noninteractive.corner_radius = radius;
    for (state, fill) in [
        (&mut widgets.inactive, SURFACE_2),
        (&mut widgets.hovered, SURFACE_3),
        (&mut widgets.active, SURFACE_3),
        (&mut widgets.open, SURFACE_3),
    ] {
        state.bg_fill = fill;
        state.weak_bg_fill = fill;
        state.fg_stroke = Stroke::new(HAIRLINE, FG);
        state.corner_radius = radius;
    }
    widgets.inactive.bg_stroke = Stroke::new(HAIRLINE, BORDER);
    widgets.hovered.bg_stroke = Stroke::new(HAIRLINE, MUTED);
    widgets.active.bg_stroke = Stroke::new(HAIRLINE, ACCENT);
    widgets.open.bg_stroke = Stroke::new(HAIRLINE, ACCENT);
    ctx.set_visuals(visuals);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn uses_the_tape_and_console_tokens() {
        assert_eq!(BG, Color32::from_hex("#0c0b0a").unwrap());
        assert_eq!(FG, Color32::from_hex("#f1e9dc").unwrap());
        assert_eq!(ACCENT, Color32::from_hex("#ff6a3d").unwrap());
        assert_eq!(LINK, Color32::from_hex("#5b7cff").unwrap());
    }
}

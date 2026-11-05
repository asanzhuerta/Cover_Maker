//! Client of the local Cover_Maker engine (ADR-008).
//!
//! The engine writes `%LOCALAPPDATA%\Cover_Maker\run\engine.json` with its
//! port and a client token while it runs. Every request carries the token in
//! the `Authorization` header and addresses `127.0.0.1:<port>`, which is the
//! exact `Host` the engine checks.

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use std::time::Duration;

use serde::{Deserialize, Serialize};

/// Stems the engine can separate, in display order.
pub const STEMS: [&str; 6] = ["vocals", "drums", "bass", "guitar", "piano", "other"];

#[derive(Clone, Debug, Deserialize, PartialEq)]
pub struct Discovery {
    pub port: u16,
    pub token: String,
    pub pid: u32,
    pub version: String,
    #[serde(default = "default_host")]
    pub host: String,
    #[serde(default)]
    pub schema: u32,
}

fn default_host() -> String {
    "127.0.0.1".into()
}

/// `%LOCALAPPDATA%\Cover_Maker`, or `COVER_MAKER_HOME` when set.
pub fn home() -> PathBuf {
    if let Some(dir) = std::env::var_os("COVER_MAKER_HOME").filter(|v| !v.is_empty()) {
        return PathBuf::from(dir);
    }
    let base = std::env::var_os("LOCALAPPDATA")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("."));
    base.join("Cover_Maker")
}

pub fn read_discovery(home: &Path) -> Option<Discovery> {
    let text = std::fs::read_to_string(home.join("run").join("engine.json")).ok()?;
    let info: Discovery = serde_json::from_str(&text).ok()?;
    // Only loopback: never send the token anywhere else.
    (info.host == "127.0.0.1").then_some(info)
}

#[derive(Debug, Serialize, PartialEq)]
pub struct JobRequest {
    pub inputs: Vec<String>,
    pub stems: Vec<String>,
    pub mode: &'static str,
    pub output_dir: String,
    pub rights_confirmed: bool,
}

impl JobRequest {
    pub fn new(input: &str, stems: &[String], output_dir: &Path, rights: bool) -> Self {
        Self {
            inputs: vec![input.trim().to_string()],
            stems: stems.to_vec(),
            mode: "extract",
            output_dir: output_dir.to_string_lossy().into_owned(),
            rights_confirmed: rights,
        }
    }
}

#[derive(Debug, Deserialize)]
struct JobCreated {
    job_id: i64,
}

#[derive(Debug, Deserialize)]
struct ApiError {
    #[serde(default)]
    detail: String,
    #[serde(default)]
    code: String,
    #[serde(default)]
    models: Vec<String>,
}

#[derive(Clone, Debug, Deserialize, PartialEq)]
pub struct Item {
    pub status: String,
    #[serde(default)]
    pub current_step: Option<String>,
    #[serde(default)]
    pub outputs: BTreeMap<String, String>,
    #[serde(default)]
    pub error: Option<String>,
}

#[derive(Clone, Debug, Deserialize, PartialEq)]
pub struct Job {
    pub status: String,
    #[serde(default)]
    pub error: Option<String>,
    #[serde(default)]
    pub item_list: Vec<Item>,
}

impl Job {
    pub fn finished(&self) -> bool {
        matches!(self.status.as_str(), "done" | "failed" | "cancelled")
    }

    /// Stem files of the first song, in the order the stems were asked for.
    pub fn stems(&self, wanted: &[String]) -> Vec<(String, PathBuf)> {
        let Some(item) = self.item_list.first() else {
            return Vec::new();
        };
        let rank = |name: &str| {
            wanted
                .iter()
                .position(|w| w.eq_ignore_ascii_case(name))
                .unwrap_or(usize::MAX)
        };
        let mut out: Vec<_> = item
            .outputs
            .iter()
            .map(|(name, path)| (name.clone(), PathBuf::from(path)))
            .collect();
        out.sort_by_key(|(name, _)| (rank(name), name.to_lowercase()));
        out
    }

    /// One line for the status bar.
    pub fn describe(&self) -> String {
        let item = self.item_list.first();
        match self.status.as_str() {
            "done" => "Done".into(),
            "failed" => format!(
                "Failed: {}",
                item.and_then(|i| i.error.clone())
                    .or_else(|| self.error.clone())
                    .unwrap_or_default()
            ),
            "cancelled" => "Cancelled".into(),
            other => match item.and_then(|i| i.current_step.clone()) {
                Some(step) => format!("Working: {step}"),
                None => format!("Working ({other})"),
            },
        }
    }
}

/// Turns an error response into a message for the user.
pub fn explain(status: u16, body: &str) -> String {
    let err: Option<ApiError> = serde_json::from_str(body).ok();
    match err {
        Some(e) if e.code == "model_not_installed" => format!(
            "Install the required models in Cover_Maker first ({}).",
            e.models.join(", ")
        ),
        Some(e) if e.code == "rights_required" => {
            "Links need you to confirm that you have the rights to the audio.".into()
        }
        Some(e) if !e.detail.is_empty() => e.detail,
        _ => format!("Cover_Maker answered {status}."),
    }
}

pub struct Client {
    info: Discovery,
    agent: ureq::Agent,
}

impl Client {
    pub fn new(info: Discovery) -> Self {
        let agent = ureq::AgentBuilder::new()
            .timeout(Duration::from_secs(60))
            // Never follow redirects: the token must stay on loopback.
            .redirects(0)
            .build();
        Self { info, agent }
    }

    pub fn connect() -> Result<Self, String> {
        let info = read_discovery(&home())
            .ok_or_else(|| "Cover_Maker is not running. Open the app first.".to_string())?;
        let client = Self::new(info);
        client.health()?;
        Ok(client)
    }

    fn url(&self, path: &str) -> String {
        format!("http://127.0.0.1:{}{}", self.info.port, path)
    }

    fn auth(&self) -> String {
        format!("Bearer {}", self.info.token)
    }

    fn call(&self, req: ureq::Request, body: Option<&JobRequest>) -> Result<String, String> {
        let req = req.set("Authorization", &self.auth());
        let result = match body {
            Some(b) => req.send_json(b),
            None => req.call(),
        };
        match result {
            Ok(resp) => resp.into_string().map_err(|e| e.to_string()),
            Err(ureq::Error::Status(code, resp)) => {
                Err(explain(code, &resp.into_string().unwrap_or_default()))
            }
            Err(e) => Err(format!("Cannot reach Cover_Maker: {e}")),
        }
    }

    pub fn health(&self) -> Result<(), String> {
        self.call(self.agent.get(&self.url("/health")), None)
            .map(|_| ())
            .map_err(|_| "Cover_Maker is not answering. Restart the app.".to_string())
    }

    pub fn submit(&self, job: &JobRequest) -> Result<i64, String> {
        let text = self.call(self.agent.post(&self.url("/jobs")), Some(job))?;
        serde_json::from_str::<JobCreated>(&text)
            .map(|c| c.job_id)
            .map_err(|e| e.to_string())
    }

    pub fn job(&self, id: i64) -> Result<Job, String> {
        let text = self.call(self.agent.get(&self.url(&format!("/jobs/{id}"))), None)?;
        serde_json::from_str(&text).map_err(|e| e.to_string())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reads_discovery_and_rejects_other_hosts() {
        let dir = std::env::temp_dir().join(format!("cm-vst3-test-{}", std::process::id()));
        std::fs::create_dir_all(dir.join("run")).unwrap();
        let file = dir.join("run").join("engine.json");
        std::fs::write(
            &file,
            r#"{"port": 5000, "token": "abc", "pid": 1, "version": "1.0.0", "host": "127.0.0.1", "schema": 1}"#,
        )
        .unwrap();
        let info = read_discovery(&dir).unwrap();
        assert_eq!(info.port, 5000);
        assert_eq!(info.token, "abc");
        std::fs::write(
            &file,
            r#"{"port": 5000, "token": "abc", "pid": 1, "version": "1", "host": "evil.example"}"#,
        )
        .unwrap();
        assert!(read_discovery(&dir).is_none());
        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn builds_the_job_request() {
        let req = JobRequest::new(
            " C:\\song.wav ",
            &["vocals".into()],
            Path::new("C:\\out"),
            false,
        );
        let json = serde_json::to_value(&req).unwrap();
        assert_eq!(json["inputs"][0], "C:\\song.wav");
        assert_eq!(json["mode"], "extract");
        assert_eq!(json["stems"][0], "vocals");
        assert_eq!(json["rights_confirmed"], false);
    }

    #[test]
    fn orders_stems_as_asked_and_describes_progress() {
        let job: Job = serde_json::from_str(
            r#"{"status": "done", "item_list": [{"status": "done", "outputs":
                {"Bass": "b.wav", "Vocals": "v.wav", "Other": "o.wav"}}]}"#,
        )
        .unwrap();
        let names: Vec<_> = job
            .stems(&["vocals".into(), "bass".into()])
            .into_iter()
            .map(|(n, _)| n)
            .collect();
        assert_eq!(names, ["Vocals", "Bass", "Other"]);
        assert!(job.finished());
        let running: Job = serde_json::from_str(
            r#"{"status": "running", "item_list": [{"status": "running", "current_step": "separate"}]}"#,
        )
        .unwrap();
        assert!(!running.finished());
        assert_eq!(running.describe(), "Working: separate");
    }

    #[test]
    fn explains_engine_errors() {
        let body = r#"{"detail": "x", "code": "model_not_installed", "models": ["htdemucs"]}"#;
        assert!(explain(409, body).contains("htdemucs"));
        assert!(explain(400, r#"{"detail": "", "code": "rights_required"}"#).contains("rights"));
        assert_eq!(explain(500, "oops"), "Cover_Maker answered 500.");
    }
}

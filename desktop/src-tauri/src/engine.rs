//! Lifecycle of the Python engine process.
//!
//! The shell generates a per-session token, starts `cover-maker serve` with the
//! token and its own PID in the environment, assigns the process to a
//! kill-on-close Job Object and waits for the handshake line printed on stdout.

use std::io::{BufRead, BufReader};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::sync::mpsc;
use std::time::Duration;

use serde::{Deserialize, Serialize};

use crate::jobobject::KillOnCloseJob;

const HANDSHAKE_TIMEOUT: Duration = Duration::from_secs(60);
#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;

/// What the UI needs to talk to the engine.
#[derive(Clone, Debug, Serialize)]
pub struct EngineInfo {
    pub port: u16,
    pub token: String,
    pub pid: u32,
    pub version: String,
}

#[derive(Debug, Deserialize)]
struct Handshake {
    event: String,
    port: u16,
    pid: u32,
    version: String,
}

pub struct Engine {
    pub info: EngineInfo,
    child: Child,
    _job: KillOnCloseJob,
}

impl Engine {
    pub fn kill(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

#[derive(Default)]
pub struct EngineState(pub Mutex<Option<Engine>>);

/// Parse one stdout line; returns the handshake if it is the ready event.
fn parse_handshake(line: &str) -> Option<Handshake> {
    serde_json::from_str::<Handshake>(line.trim())
        .ok()
        .filter(|h| h.event == "ready")
}

/// 32 random bytes as 64 hex characters.
pub fn new_token() -> String {
    let mut bytes = [0u8; 32];
    getrandom::fill(&mut bytes).expect("OS random generator unavailable");
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

/// Directory of the engine project used in development builds.
fn dev_engine_dir() -> PathBuf {
    std::env::var_os("COVER_MAKER_ENGINE_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../engine"))
}

fn engine_command(token: &str) -> Command {
    let mut command = Command::new("uv");
    command
        .args(["run", "--project"])
        .arg(dev_engine_dir())
        .args(["cover-maker", "serve"])
        .env("COVER_MAKER_TOKEN", token)
        .env("COVER_MAKER_PARENT_PID", std::process::id().to_string())
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::inherit());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(CREATE_NO_WINDOW);
    }
    command
}

/// Start the engine and block until it announces its port.
pub fn start() -> Result<Engine, String> {
    let job = KillOnCloseJob::new().map_err(|e| format!("cannot create job object: {e}"))?;
    let token = new_token();
    let mut child = engine_command(&token)
        .spawn()
        .map_err(|e| format!("cannot start engine (is uv installed?): {e}"))?;
    job.assign(&child)
        .map_err(|e| format!("cannot assign engine to job object: {e}"))?;

    let stdout = child.stdout.take().ok_or("engine stdout unavailable")?;
    let (tx, rx) = mpsc::channel();
    std::thread::spawn(move || {
        let mut sent = false;
        for line in BufReader::new(stdout).lines().map_while(Result::ok) {
            if !sent && let Some(handshake) = parse_handshake(&line) {
                let _ = tx.send(handshake);
                sent = true;
            }
            // Keep draining stdout so the engine never blocks on a full pipe.
        }
    });

    match rx.recv_timeout(HANDSHAKE_TIMEOUT) {
        Ok(handshake) => Ok(Engine {
            info: EngineInfo {
                port: handshake.port,
                token,
                pid: handshake.pid,
                version: handshake.version,
            },
            child,
            _job: job,
        }),
        Err(_) => {
            let _ = child.kill();
            Err("engine did not report ready in time".into())
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_ready_handshake() {
        let line = r#"{"event": "ready", "port": 51234, "pid": 42, "version": "0.2.0"}"#;
        let handshake = parse_handshake(line).expect("handshake");
        assert_eq!(handshake.port, 51234);
        assert_eq!(handshake.pid, 42);
    }

    #[test]
    fn ignores_other_lines() {
        assert!(parse_handshake("INFO starting").is_none());
        assert!(
            parse_handshake(r#"{"event": "log", "port": 1, "pid": 1, "version": "x"}"#).is_none()
        );
    }

    #[test]
    fn token_is_64_hex_chars_and_random() {
        let a = new_token();
        assert_eq!(a.len(), 64);
        assert!(a.chars().all(|c| c.is_ascii_hexdigit()));
        assert_ne!(a, new_token());
    }
}

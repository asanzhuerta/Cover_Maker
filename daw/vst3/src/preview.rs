//! Stem preview played through the plugin's output.
//!
//! A stem is decoded once (WAV, the engine's default export) into stereo f32
//! and read with linear interpolation so it plays at the right pitch whatever
//! the host sample rate is.

use std::path::Path;

pub struct Preview {
    /// Interleaved stereo samples.
    samples: Vec<f32>,
    rate: f32,
    position: f64,
    pub playing: bool,
}

impl Preview {
    pub fn from_samples(samples: Vec<f32>, rate: f32) -> Self {
        Self {
            samples,
            rate,
            position: 0.0,
            playing: true,
        }
    }

    /// Decodes a WAV file to stereo (mono is duplicated, extra channels dropped).
    pub fn load(path: &Path) -> Result<Self, String> {
        let mut reader = hound::WavReader::open(path).map_err(|e| e.to_string())?;
        let spec = reader.spec();
        let channels = spec.channels.max(1) as usize;
        let raw: Vec<f32> = match spec.sample_format {
            hound::SampleFormat::Float => reader
                .samples::<f32>()
                .collect::<Result<_, _>>()
                .map_err(|e| e.to_string())?,
            hound::SampleFormat::Int => {
                let scale = 1.0 / (1u64 << (spec.bits_per_sample - 1)) as f32;
                reader
                    .samples::<i32>()
                    .map(|s| s.map(|v| v as f32 * scale))
                    .collect::<Result<_, _>>()
                    .map_err(|e| e.to_string())?
            }
        };
        let mut samples = Vec::with_capacity(raw.len() / channels * 2);
        for frame in raw.chunks(channels) {
            let left = frame[0];
            let right = if channels > 1 { frame[1] } else { left };
            samples.push(left);
            samples.push(right);
        }
        Ok(Self::from_samples(samples, spec.sample_rate as f32))
    }

    pub fn frames(&self) -> usize {
        self.samples.len() / 2
    }

    pub fn seconds(&self) -> f32 {
        self.frames() as f32 / self.rate
    }

    pub fn elapsed(&self) -> f32 {
        self.position as f32 / self.rate
    }

    pub fn rewind(&mut self) {
        self.position = 0.0;
    }

    /// Adds the next frame at `host_rate` to `out`; stops at the end.
    pub fn next_frame(&mut self, host_rate: f32, gain: f32) -> (f32, f32) {
        let frames = self.frames();
        if !self.playing || frames < 2 {
            return (0.0, 0.0);
        }
        let index = self.position as usize;
        if index + 1 >= frames {
            self.playing = false;
            self.position = 0.0;
            return (0.0, 0.0);
        }
        let frac = (self.position - index as f64) as f32;
        let at = |i: usize, ch: usize| self.samples[i * 2 + ch];
        let l = at(index, 0) + (at(index + 1, 0) - at(index, 0)) * frac;
        let r = at(index, 1) + (at(index + 1, 1) - at(index, 1)) * frac;
        self.position += (self.rate / host_rate) as f64;
        (l * gain, r * gain)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn resamples_and_stops_at_the_end() {
        // 4 frames ramp at 10 Hz played at 20 Hz -> half steps.
        let mut p = Preview::from_samples(vec![0.0, 0.0, 1.0, 1.0, 2.0, 2.0, 3.0, 3.0], 10.0);
        let got: Vec<f32> = (0..6).map(|_| p.next_frame(20.0, 1.0).0).collect();
        assert_eq!(got, [0.0, 0.5, 1.0, 1.5, 2.0, 2.5]);
        assert_eq!(p.next_frame(20.0, 1.0), (0.0, 0.0));
        assert!(!p.playing);
    }

    #[test]
    fn loads_mono_wav_as_stereo() {
        let path = std::env::temp_dir().join(format!("cm-vst3-{}.wav", std::process::id()));
        let spec = hound::WavSpec {
            channels: 1,
            sample_rate: 8000,
            bits_per_sample: 16,
            sample_format: hound::SampleFormat::Int,
        };
        let mut writer = hound::WavWriter::create(&path, spec).unwrap();
        for v in [0i16, 16384, -16384] {
            writer.write_sample(v).unwrap();
        }
        writer.finalize().unwrap();
        let p = Preview::load(&path).unwrap();
        assert_eq!(p.frames(), 3);
        assert_eq!(p.samples, [0.0, 0.0, 0.5, 0.5, -0.5, -0.5]);
        std::fs::remove_file(path).unwrap();
    }
}

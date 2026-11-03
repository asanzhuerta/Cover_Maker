# Changelog

All notable changes to this project are documented in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Start of the v2 rewrite: local, legal-by-design stem separation desktop app.
- MIT licence, README and disclaimer.
- Monorepo skeleton: Python engine (`engine/`, uv, ruff, pyright, pytest) with a
  `cover-maker` CLI, and Tauri 2 + SvelteKit desktop shell (`desktop/`).
- GitHub Actions CI for engine, UI and shell on Windows, and LaTeX docs on Ubuntu.
- LaTeX documentation set with a shared `covermaker` class: Project Plan, SRS,
  Architecture & Design, Test Plan, Installation Guide and User Manual; tables
  generated from `docs/data/*.yaml`.
- Contribution guide, security policy, code of conduct, issue/PR templates and
  Dependabot configuration.

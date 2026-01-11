// Prevents additional console window on Windows in release builds
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use hex::FromHex;
use sha2::{Digest, Sha256};
use std::fs;
use std::fs::File;
use std::io::{Read, Write};
use std::path::PathBuf;
use std::sync::Arc;
use std::time::Duration;
use sysinfo::{Components, System, SystemExt};
use tauri::api::process::{Command, CommandChild, CommandEvent};
use tauri::{Manager, State};
use tokio::sync::Mutex;

struct SidecarState {
    process: Option<CommandChild>,
    port: u16,
    health_task_running: bool,
    resource_task_running: bool,
}

impl SidecarState {
    fn new() -> Self {
        Self {
            process: None,
            port: 8000,
            health_task_running: false,
            resource_task_running: false,
        }
    }
}

#[tauri::command]
async fn check_sidecar_health(port: u16) -> Result<bool, String> {
    // Simple health check - try to connect to the WebSocket port
    use tokio::net::TcpStream;
    
    match tokio::time::timeout(
        Duration::from_secs(2),
        TcpStream::connect(format!("127.0.0.1:{}", port))
    ).await {
        Ok(Ok(_)) => Ok(true),
        Ok(Err(_)) => Ok(false),
        Err(_) => Ok(false),
    }
}

fn sidecar_filename() -> &'static str {
    if cfg!(windows) {
        "project-dawn-server.exe"
    } else {
        "project-dawn-server"
    }
}

fn resolve_sidecar_paths(app_handle: &tauri::AppHandle) -> Option<(PathBuf, PathBuf)> {
    let resource_dir = app_handle.path_resolver().resource_dir()?;
    let sidecar_path = resource_dir.join("sidecar").join(sidecar_filename());
    let checksum_path = sidecar_path.with_file_name(format!(
        "{}.sha256",
        sidecar_path.file_name()?.to_string_lossy()
    ));
    Some((sidecar_path, checksum_path))
}

fn read_checksum(checksum_path: &PathBuf) -> Result<Vec<u8>, String> {
    let contents = std::fs::read_to_string(checksum_path)
        .map_err(|e| format!("Failed to read checksum: {e}"))?;
    let digest_hex = contents
        .split_whitespace()
        .next()
        .ok_or_else(|| "Checksum file missing digest".to_string())?;
    let bytes = Vec::from_hex(digest_hex)
        .map_err(|e| format!("Invalid checksum format: {e}"))?;
    Ok(bytes)
}

fn verify_sidecar_integrity(app_handle: &tauri::AppHandle) -> Result<(), String> {
    let (sidecar_path, checksum_path) = resolve_sidecar_paths(app_handle)
        .ok_or_else(|| "Failed to resolve sidecar path".to_string())?;

    if !sidecar_path.exists() {
        return Err(format!("Sidecar executable not found: {:?}", sidecar_path));
    }
    if !checksum_path.exists() {
        return Err(format!("Sidecar checksum not found: {:?}", checksum_path));
    }

    let expected = read_checksum(&checksum_path)?;
    let mut file = File::open(&sidecar_path)
        .map_err(|e| format!("Failed to open sidecar: {e}"))?;
    let mut hasher = Sha256::new();
    let mut buffer = [0u8; 1024 * 1024];
    loop {
        let read = file.read(&mut buffer).map_err(|e| format!("Failed to read sidecar: {e}"))?;
        if read == 0 {
            break;
        }
        hasher.update(&buffer[..read]);
    }
    let actual = hasher.finalize().to_vec();
    if actual != expected {
        return Err("Sidecar checksum mismatch".to_string());
    }
    Ok(())
}

async fn start_health_monitor(state: Arc<Mutex<SidecarState>>) {
    let mut guard = state.lock().await;
    if guard.health_task_running {
        return;
    }
    guard.health_task_running = true;
    let port = guard.port;
    drop(guard);

    tauri::async_runtime::spawn(async move {
        loop {
            tokio::time::sleep(Duration::from_secs(5)).await;
            match check_sidecar_health(port).await {
                Ok(true) => {}
                Ok(false) | Err(_) => {
                    eprintln!("[Tauri] Sidecar health check failed on port {}", port);
                }
            }
        }
    });
}

#[tauri::command]
async fn sidecar_status(state: State<'_, Arc<Mutex<SidecarState>>>) -> Result<bool, String> {
    let guard = state.lock().await;
    Ok(guard.process.is_some())
}

#[tauri::command]
async fn start_sidecar(
    state: State<'_, Arc<Mutex<SidecarState>>>,
    app: tauri::AppHandle,
) -> Result<bool, String> {
    let mut guard = state.lock().await;
    if guard.process.is_some() {
        return Ok(true);
    }

    if let Err(err) = verify_sidecar_integrity(&app) {
        return Err(err);
    }

    let data_root = data_root(&app);
    let (mut rx, child) = Command::new_sidecar("project-dawn-server")
        .map_err(|e| format!("Failed to configure sidecar: {e}"))?
        .env("PROJECT_DAWN_DATA_ROOT", data_root.to_string_lossy().to_string())
        .spawn()
        .map_err(|e| format!("Failed to start sidecar: {e}"))?;

    guard.process = Some(child);
    drop(guard);

    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(line) => println!("[sidecar] {}", line),
                CommandEvent::Stderr(line) => eprintln!("[sidecar] {}", line),
                CommandEvent::Error(err) => eprintln!("[sidecar] error: {}", err),
                _ => {}
            }
        }
    });

    start_health_monitor(state.inner().clone()).await;
    Ok(true)
}

#[tauri::command]
async fn stop_sidecar(state: State<'_, Arc<Mutex<SidecarState>>>) -> Result<bool, String> {
    let mut guard = state.lock().await;
    if let Some(child) = guard.process.take() {
        let _ = child.kill();
        Ok(true)
    } else {
        Ok(false)
    }
}

fn data_root(app: &tauri::AppHandle) -> PathBuf {
    if let Ok(override_path) = std::env::var("PROJECT_DAWN_DATA_ROOT") {
        return PathBuf::from(override_path);
    }
    tauri::api::path::app_data_dir(&app.config())
        .unwrap_or_else(|| std::env::current_dir().unwrap_or_else(|_| PathBuf::from(".")))
}

fn write_json_atomic(path: &PathBuf, payload: &str) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)
            .map_err(|e| format!("Failed to create {}: {e}", parent.display()))?;
    }
    let tmp_path = path.with_extension("tmp");
    let mut handle = File::create(&tmp_path)
        .map_err(|e| format!("Failed to create {}: {e}", tmp_path.display()))?;
    handle
        .write_all(payload.as_bytes())
        .map_err(|e| format!("Failed to write {}: {e}", tmp_path.display()))?;
    handle
        .write_all(b"\n")
        .map_err(|e| format!("Failed to write newline: {e}"))?;
    handle.flush().map_err(|e| format!("Failed to flush: {e}"))?;
    handle
        .sync_all()
        .map_err(|e| format!("Failed to sync: {e}"))?;
    fs::rename(&tmp_path, path)
        .map_err(|e| format!("Failed to move {}: {e}", path.display()))?;
    Ok(())
}

fn read_optional_file(path: PathBuf) -> Result<Option<String>, String> {
    if !path.exists() {
        return Ok(None);
    }
    fs::read_to_string(&path)
        .map(Some)
        .map_err(|e| format!("Failed to read {}: {e}", path.display()))
}

#[tauri::command]
fn get_manifest(app: tauri::AppHandle) -> Result<Option<String>, String> {
    let path = data_root(&app).join("vault").join("manifest.json");
    read_optional_file(path)
}

#[tauri::command]
fn get_peers(app: tauri::AppHandle) -> Result<Option<String>, String> {
    let path = data_root(&app).join("mesh").join("peers.json");
    read_optional_file(path)
}

#[tauri::command]
fn get_feed(app: tauri::AppHandle, limit: usize) -> Result<Vec<String>, String> {
    let path = data_root(&app).join("mesh").join("agent_feed.jsonl");
    if !path.exists() {
        return Ok(Vec::new());
    }
    let contents = fs::read_to_string(&path)
        .map_err(|e| format!("Failed to read {}: {e}", path.display()))?;
    let mut lines: Vec<String> = contents.lines().map(|line| line.to_string()).collect();
    if lines.len() > limit {
        lines = lines.split_off(lines.len() - limit);
    }
    Ok(lines)
}

#[tauri::command]
fn get_resource_state(app: tauri::AppHandle) -> Result<Option<String>, String> {
    let path = data_root(&app).join("mesh").join("resource_state.json");
    read_optional_file(path)
}

fn read_battery_status() -> (Option<f32>, Option<bool>) {
    let base = PathBuf::from("/sys/class/power_supply");
    if !base.exists() {
        return (None, None);
    }

    let mut battery_pct = None;
    let mut on_ac = None;

    if let Ok(entries) = fs::read_dir(base) {
        for entry in entries.flatten() {
            let path = entry.path();
            let kind = fs::read_to_string(path.join("type")).unwrap_or_default();
            let kind = kind.trim();
            if kind == "Battery" {
                let capacity = fs::read_to_string(path.join("capacity")).unwrap_or_default();
                if let Ok(value) = capacity.trim().parse::<f32>() {
                    battery_pct = Some(value);
                }
            } else if kind == "Mains" || kind == "AC" {
                let online = fs::read_to_string(path.join("online")).unwrap_or_default();
                if let Ok(value) = online.trim().parse::<u8>() {
                    on_ac = Some(value == 1);
                }
            }
        }
    }

    (battery_pct, on_ac)
}

fn read_cpu_temp(components: &Components) -> Option<f32> {
    components
        .iter()
        .find(|component| component.label().to_lowercase().contains("cpu"))
        .map(|component| component.temperature())
}

async fn start_resource_monitor(app: tauri::AppHandle, state: Arc<Mutex<SidecarState>>) {
    let mut guard = state.lock().await;
    if guard.resource_task_running {
        return;
    }
    guard.resource_task_running = true;
    drop(guard);
    let data_root = data_root(&app);

    tauri::async_runtime::spawn(async move {
        let mut system = System::new_all();
        let mut components = Components::new_with_refreshed_list();
        loop {
            system.refresh_cpu();
            components.refresh();

            let cpu_usage = system.global_cpu_info().cpu_usage();
            let cpu_temp = read_cpu_temp(&components);
            let (battery_pct, on_ac_power) = read_battery_status();

            let throttled = cpu_usage > 70.0
                || cpu_temp.map(|temp| temp > 85.0).unwrap_or(false)
                || battery_pct
                    .zip(on_ac_power)
                    .map(|(pct, ac)| pct < 30.0 && !ac)
                    .unwrap_or(false);

            let payload = serde_json::json!({
                "timestamp": chrono::Utc::now().timestamp(),
                "cpu_usage_pct": cpu_usage,
                "cpu_temp_c": cpu_temp,
                "battery_pct": battery_pct,
                "on_ac_power": on_ac_power,
                "throttled": throttled,
            });

            let target = data_root.join("mesh").join("resource_state.json");
            let _ = write_json_atomic(&target, &payload.to_string());
            let _ = app.emit_all("resource_state", payload);

            tokio::time::sleep(Duration::from_secs(5)).await;
        }
    });
}

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            let sidecar_state = Arc::new(Mutex::new(SidecarState::new()));
            app.manage(sidecar_state.clone());

            let app_handle = app.handle();
            tauri::async_runtime::spawn(start_resource_monitor(
                app_handle,
                sidecar_state.clone(),
            ));
            
            // Cleanup on app exit
            app.listen_global("tauri://close-requested", move |_event| {
                let state = sidecar_state.clone();
                tauri::async_runtime::spawn(async move {
                    let mut state = state.lock().await;
                    if let Some(process) = state.process.take() {
                        println!("[Tauri] Stopping sidecar process...");
                        let _ = process.kill();
                        println!("[Tauri] Sidecar stopped");
                    }
                });
            });
            
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            check_sidecar_health,
            get_manifest,
            get_peers,
            get_feed,
            get_resource_state,
            sidecar_status,
            start_sidecar,
            stop_sidecar
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

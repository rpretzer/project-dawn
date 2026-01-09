// Prevents additional console window on Windows in release builds
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::Manager;
use std::process::{Command, Stdio};
use std::sync::Arc;
use tokio::sync::Mutex;
use std::time::Duration;
use std::path::PathBuf;

struct SidecarState {
    process: Option<std::process::Child>,
    port: u16,
}

impl SidecarState {
    fn new() -> Self {
        Self {
            process: None,
            port: 8000,
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

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            let app_handle = app.handle().clone();
            
            // Get the sidecar executable path
            let sidecar_path = app_handle
                .path_resolver()
                .resource_dir()
                .map(|dir| dir.join("sidecar").join("project-dawn-server"));
            
            // For development, try to use Python directly if sidecar doesn't exist
            let use_python = sidecar_path.as_ref()
                .map(|p| !p.exists())
                .unwrap_or(true);
            
            let sidecar_state = Arc::new(Mutex::new(SidecarState::new()));
            let state_clone = sidecar_state.clone();
            let app_handle_clone = app_handle.clone();
            
            // Spawn sidecar process
            tauri::async_runtime::spawn(async move {
                let mut state = state_clone.lock().await;
                
                if use_python {
                    // Development mode: run Python server directly
                    println!("[Tauri] Starting Python server in development mode...");
                    
                    let python_cmd = if cfg!(windows) {
                        "python"
                    } else {
                        "python3"
                    };
                    
                    // Try to find server_p2p.py relative to the Tauri app
                    let server_path = app_handle_clone
                        .path_resolver()
                        .app_dir()
                        .and_then(|dir| dir.parent().map(|p| p.join("server_p2p.py")))
                        .or_else(|| {
                            // Fallback: try current directory
                            std::env::current_dir()
                                .ok()
                                .map(|dir| dir.join("server_p2p.py"))
                        });
                    
                    if let Some(server_path) = server_path {
                        if server_path.exists() {
                            if let Some(parent) = server_path.parent() {
                                match Command::new(python_cmd)
                                    .arg(server_path.to_str().unwrap())
                                    .current_dir(parent)
                                    .stdout(Stdio::piped())
                                    .stderr(Stdio::piped())
                                    .spawn()
                                {
                                    Ok(child) => {
                                        println!("[Tauri] Python server started (PID: {})", child.id());
                                        state.process = Some(child);
                                    }
                                    Err(e) => {
                                        eprintln!("[Tauri] Failed to start Python server: {}", e);
                                    }
                                }
                            }
                        } else {
                            eprintln!("[Tauri] Server script not found: {:?}", server_path);
                        }
                    } else {
                        eprintln!("[Tauri] Could not determine server script path");
                    }
                } else if let Some(ref sidecar_path) = sidecar_path {
                    // Production mode: use sidecar executable
                    println!("[Tauri] Starting sidecar executable: {:?}", sidecar_path);
                    
                    match Command::new(sidecar_path)
                        .stdout(Stdio::piped())
                        .stderr(Stdio::piped())
                        .spawn()
                    {
                        Ok(child) => {
                            println!("[Tauri] Sidecar started (PID: {})", child.id());
                            state.process = Some(child);
                        }
                        Err(e) => {
                            eprintln!("[Tauri] Failed to start sidecar: {}", e);
                        }
                    }
                } else {
                    eprintln!("[Tauri] No sidecar path available");
                }
                
                // Health check loop
                let port = state.port;
                drop(state);
                
                loop {
                    tokio::time::sleep(Duration::from_secs(5)).await;
                    
                    match check_sidecar_health(port).await {
                        Ok(true) => {
                            // Server is healthy
                        }
                        Ok(false) | Err(_) => {
                            eprintln!("[Tauri] Sidecar health check failed on port {}", port);
                            // Could restart sidecar here if needed
                        }
                    }
                }
            });
            
            // Cleanup on app exit
            app.handle().listen("tauri://close-requested", move |_event| {
                let state = sidecar_state.clone();
                tauri::async_runtime::spawn(async move {
                    let mut state = state.lock().await;
                    if let Some(mut process) = state.process.take() {
                        println!("[Tauri] Stopping sidecar process...");
                        let _ = process.kill();
                        let _ = process.wait();
                        println!("[Tauri] Sidecar stopped");
                    }
                });
            });
            
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![check_sidecar_health])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

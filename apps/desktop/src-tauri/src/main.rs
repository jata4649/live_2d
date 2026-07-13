// AutoLive2D Layer Studio デスクトップシェル(Tauri v2)。
//
// 設計方針(docs/02): シェルはウィンドウ表示とバックエンド起動のみを担い、
// アプリ本体はブラウザでも動作する React + FastAPI に置く。
//
// バックエンド起動:
// - 環境変数 ALS_API_DIR が指す場所で `python3 -m uvicorn main:app` を起動する
//   (未設定なら何もしない = uvicorn を別途起動する開発スタイル)
// - 終了時に子プロセスを kill する
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::{Child, Command};
use std::sync::Mutex;

use tauri::Manager;

struct Backend(Mutex<Option<Child>>);

fn spawn_backend() -> Option<Child> {
    let api_dir = std::env::var("ALS_API_DIR").ok()?;
    let port = std::env::var("ALS_PORT").unwrap_or_else(|_| "8787".into());
    Command::new("python3")
        .args(["-m", "uvicorn", "main:app", "--port", &port])
        .current_dir(api_dir)
        .spawn()
        .map_err(|e| eprintln!("バックエンドの起動に失敗しました: {e}"))
        .ok()
}

fn main() {
    let backend = Backend(Mutex::new(spawn_backend()));

    tauri::Builder::default()
        .manage(backend)
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app, event| {
            if let tauri::RunEvent::Exit = event {
                let state: tauri::State<Backend> = app.state();
                let child: Option<Child> = state.0.lock().unwrap().take();
                if let Some(mut child) = child {
                    let _ = child.kill();
                }
            }
        });
}

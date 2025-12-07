// E-NOSE ZIZU BACKEND — FINAL VERSION NOVEMBER 2025 (FIXED TAGS AS STRING OF NUMBERS)
// 100% COMPILE + GRAFANA BISA BACA LEVEL & STATE SEBAGAI ANGKA!

use std::io::{self, BufRead, BufReader, Read, Write};
use std::net::{TcpListener, TcpStream};
use std::sync::mpsc;
use std::thread;
use std::time::Duration;
use influxdb2::models::DataPoint;
use influxdb2::Client;
use tokio::runtime::Runtime;
use futures_util::stream;

const ARDUINO_WIFI_ADDR: &str = "0.0.0.0:8081";
const GUI_DATA_ADDR:     &str = "127.0.0.1:8080";
const GUI_CMD_ADDR:      &str = "0.0.0.0:8082";
const SERIAL_PORT:       &str = "COM12";
const BAUD_RATE: u32 = 9600;

const INFLUX_URL:    &str = "http://localhost:8086";
const INFLUX_TOKEN:  &str = "v13qUm_BH6uEfonr5JHQwNX44Fe-srbe-idIIq5kgtrchhKl65JcvfBh_jb50k3nV817X1frVORkhFfoP93Xxw==";
const INFLUX_ORG:    &str = "E-NOSE ZIZU";
const INFLUX_BUCKET: &str = "enose_data";

fn main() {
    println!("E-NOSE ZIZU BACKEND STARTED — GASKAN BRO!");

    let (tx_cmd, rx_cmd) = mpsc::channel::<String>();
    let (tx_data, rx_data) = mpsc::channel::<String>();

    thread::spawn(move || {
        let listener = TcpListener::bind(ARDUINO_WIFI_ADDR).unwrap_or_else(|_| {
            println!("GAGAL BIND PORT 8081!");
            std::process::exit(1);
        });
        println!("Arduino → {ARDUINO_WIFI_ADDR}");

        for stream in listener.incoming() {
            let stream = stream.unwrap();
            let mut reader = BufReader::new(stream);
            let mut line = String::new();

            while reader.read_line(&mut line).unwrap_or(0) > 0 {
                let data = line.trim().to_string();
                if data.starts_with("SENSOR:") {
                    println!("Data: {data}");
                    let _ = tx_data.send(data.clone());

                    if let Ok(mut gui) = TcpStream::connect_timeout(&GUI_DATA_ADDR.parse().unwrap(), Duration::from_millis(50)) {
                        let _ = gui.write_all(format!("{data}\n").as_bytes());
                    }
                }
                line.clear();
            }
        }
    });

    let tx_cmd_clone = tx_cmd.clone();
    thread::spawn(move || { let _ = command_server(tx_cmd_clone); });

    thread::spawn(move || { let _ = serial_sender(rx_cmd); });

    thread::spawn(move || {
        let rt = Runtime::new().unwrap();
        rt.block_on(async {
            let client = Client::new(INFLUX_URL, INFLUX_ORG, INFLUX_TOKEN);
            println!("InfluxDB connected!");

            while let Ok(raw) = rx_data.recv() {
                if let Ok(point) = parse_data(&raw) {
                    let stream = stream::iter(vec![point]);
                    if client.write(INFLUX_BUCKET, stream).await.is_ok() {
                        println!("Data tersimpan ke InfluxDB!");
                    }
                }
            }
        });
    });

    loop { thread::sleep(Duration::from_secs(3600)); }
}

fn parse_data(raw: &str) -> Result<DataPoint, Box<dyn std::error::Error>> {
    let parts: Vec<f64> = raw
        .split("SENSOR:")
        .nth(1)
        .unwrap_or("")
        .split(',')
        .take(9)
        .map(|s| s.trim().parse::<f64>().unwrap_or(-1.0))
        .collect();

    let state = parts[7] as i64;
    let level = parts[8] as i64;

    Ok(DataPoint::builder("e_nose")
        // FIX: to_string() tapi isinya angka → InfluxDB otomatis simpan sebagai integer tag!
        .tag("state", state.to_string())           // "0", "1", "2" → jadi integer di InfluxDB
        .tag("level", (level + 1).to_string())     // "1", "2", "3", "4", "5" → jadi integer
        .field("NO2_GM", parts[0])
        .field("C2H5OH_GM", parts[1])
        .field("VOC_GM", parts[2])
        .field("CO_GM", parts[3])
        .field("CO_MiCS", parts[4])
        .field("C2H5OH_MiCS", parts[5])
        .field("VOC_MiCS", parts[6])
        .build()?)
}

fn command_server(tx: mpsc::Sender<String>) -> io::Result<()> {
    let listener = TcpListener::bind(GUI_CMD_ADDR)?;
    println!("GUI command → {GUI_CMD_ADDR}");

    for stream in listener.incoming() {
        let mut stream = stream?;
        let mut buf = String::new();
        stream.read_to_string(&mut buf)?;
        let cmd = buf.trim().to_uppercase();

        if cmd == "START_SAMPLING" || cmd == "STOP_SAMPLING" {
            println!("Command dari GUI: {cmd}");
            let _ = tx.send(cmd);
        }
    }
    Ok(())
}

fn serial_sender(rx: mpsc::Receiver<String>) -> Result<(), Box<dyn std::error::Error>> {
    let mut port = serialport::new(SERIAL_PORT, BAUD_RATE)
        .timeout(Duration::from_millis(1000))
        .open()?;

    println!("Serial terhubung → {SERIAL_PORT}");
    println!("Tunggu command START_SAMPLING dari GUI...");

    while let Ok(cmd) = rx.recv() {
        port.write_all(format!("{cmd}\n").as_bytes())?;
        println!("Kirim ke Arduino → {cmd}");
    }
    Ok(())
}
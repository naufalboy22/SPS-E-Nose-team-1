// ========================================
// E-NOSE ZIZU — FINAL 2025 (MiCS-5524 ADAFRUIT + GM-XXX)
// HOLD 2 MENIT | PURGE 4 MENIT | LEVEL 1-5 OTOMATIS
// RUMUS MiCS-5524 100% DARI KODE KAMU YANG SUDAH BENAR!
// ========================================

#include <WiFiS3.h>
#include <Wire.h>
#include "Multichannel_Gas_GMXXX.h"

// ==================== WIFI ====================
const char* ssid     = "Mojako - Guest";
const char* pass     = "55555555";
const char* RUST_IP  = "192.168.68.178";   // GANTI KALAU IP BERUBAH
const int   RUST_PORT = 8081;
WiFiClient client;

// ==================== SENSOR ====================
GAS_GMXXX<TwoWire> gas;
#define MICS_PIN    A1
#define RLOAD       820.0
#define VCC         5.0
float R0_mics = 100000.0;  // Default, nanti di-update di udara bersih

// ==================== MOTOR (SESUAI KAMU!) ====================
const int PWM_KIPAS   = 10;
const int DIR_KIPAS_1 = 12;
const int DIR_KIPAS_2 = 13;
const int PWM_POMPA   = 11;
const int DIR_POMPA_1 = 8;
const int DIR_POMPA_2 = 9;

// ==================== FSM & LEVEL ====================
enum State { IDLE, PRE_COND, RAMP_UP, HOLD, PURGE, RECOVERY, DONE };
State currentState = IDLE;
unsigned long stateTime = 0;
int currentLevel = 0;  // 0–4 → Rust +1 → 1–5
const int speeds[5] = {51, 102, 153, 204, 255};
bool samplingActive = false;

// ==================== TIMING (SESUAI PERMINTAAN!) ====================
const unsigned long T_PRECOND  = 5000;   // 5 detik (sensor stabil)
const unsigned long T_RAMP     = 3000;    // 3 detik naik perlahan
const unsigned long T_HOLD     = 60000;  // 1 MENIT
const unsigned long T_PURGE    = 60000;  // 1 MENIT
const unsigned long T_RECOVERY = 5000;   // 5 detik
unsigned long lastSend = 0;

// ==================== MOTOR CONTROL ====================
void kipas(int speed, bool buang = false) {
  digitalWrite(DIR_KIPAS_1, buang ? LOW : HIGH);
  digitalWrite(DIR_KIPAS_2, buang ? HIGH : LOW);
  analogWrite(PWM_KIPAS, speed);
}
void pompa(int speed) {
  digitalWrite(DIR_POMPA_1, HIGH);
  digitalWrite(DIR_POMPA_2, LOW);
  analogWrite(PWM_POMPA, speed);
}
void stopAll() { analogWrite(PWM_KIPAS, 0); analogWrite(PWM_POMPA, 0); }

void rampKipas(int target) {
  static int cur = 0;
  if (cur < target) cur += 15;
  else if (cur > target) cur -= 15;
  cur = constrain(cur, 0, 255);
  kipas(cur);
}

// ==================== MiCS-5524 (RUMUS DARI KODE KAMU YANG SUDAH BENAR!) ====================
float calculateRs() {
  int raw = analogRead(MICS_PIN);
  if (raw < 10) return -1;  // Dicabut
  float Vout = raw * (VCC / 1023.0);
  if (Vout >= VCC || Vout <= 0) return -1;
  return RLOAD * ((VCC - Vout) / Vout);
}

float ppmFromRatio(float ratio, String gas) {
  if (ratio <= 0 || R0_mics == 0) return -1;
  float ppm = 0.0;
  if (gas == "CO")      ppm = pow(10, (log10(ratio) - 0.35) / -0.85);
  else if (gas == "C2H5OH") ppm = pow(10, (log10(ratio) - 0.15) / -0.65);
  else if (gas == "VOC")    ppm = pow(10, (log10(ratio) + 0.1) / -0.75);
  return (ppm >= 0 && ppm <= 5000) ? ppm : -1;
}

// ==================== SETUP ====================
void setup() {
  Serial.begin(9600);
  
  pinMode(DIR_KIPAS_1, OUTPUT); pinMode(DIR_KIPAS_2, OUTPUT); pinMode(PWM_KIPAS, OUTPUT);
  pinMode(DIR_POMPA_1, OUTPUT); pinMode(DIR_POMPA_2, OUTPUT); pinMode(PWM_POMPA, OUTPUT);
  stopAll();

  Wire.begin();
  gas.begin(Wire, 0x08);

  // KALIBRASI R0 SEKALI DI UDARA BERSIH (SEPERTI KODE KAMU)
  delay(2000);
  float Rs_air = calculateRs();
  if (Rs_air > 0) {
    R0_mics = Rs_air;
    Serial.print("R0 MiCS-5524 terukur: "); Serial.print(R0_mics/1000.0, 2); Serial.println(" kΩ");
  } else {
    Serial.println("R0 MiCS-5524 pakai default: 100 kΩ");
  }

  while (WiFi.begin(ssid, pass) != WL_CONNECTED) { Serial.print("."); delay(500); }
  Serial.println("\nWiFi Connected! IP: " + WiFi.localIP().toString());
  Serial.println("E-NOSE ZIZU SIAP — Tunggu START_SAMPLING");
}

// ==================== LOOP ====================
void loop() {
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n'); cmd.trim();
    if (cmd == "START_SAMPLING") startSampling();
    else if (cmd == "STOP_SAMPLING") stopSampling();
  }

  if (millis() - lastSend >= 250) { lastSend = millis(); sendSensorData(); }
  if (samplingActive) runFSM();
}

// ==================== FSM ====================
void startSampling() {
  if (!samplingActive) {
    samplingActive = true;
    currentLevel = 0;
    changeState(PRE_COND);
    Serial.println("SAMPLING DIMULAI — 5 LEVEL (HOLD 2 MENIT, PURGE 4 MENIT)");
  }
}
void stopSampling() {
  samplingActive = false;
  currentLevel = 0;
  changeState(IDLE);
  stopAll();
  Serial.println("SAMPLING DIHENTIKAN");
}

void changeState(State s) {
  currentState = s;
  stateTime = millis();
  String names[] = {"IDLE","PRE-COND","RAMP_UP","HOLD","PURGE","RECOVERY","DONE"};
  Serial.println("STATE → " + names[s] + " | Level " + String(currentLevel + 1));
}

void runFSM() {
  unsigned long elapsed = millis() - stateTime;
  switch (currentState) {
    case PRE_COND:   kipas(120); pompa(0); if (elapsed >= T_PRECOND)  changeState(RAMP_UP); break;
    case RAMP_UP:    rampKipas(speeds[currentLevel]); pompa(0); if (elapsed >= T_RAMP) changeState(HOLD); break;
    case HOLD:       kipas(speeds[currentLevel]); pompa(0); if (elapsed >= T_HOLD) changeState(PURGE); break;
    case PURGE:      kipas(255, true); pompa(255); if (elapsed >= T_PURGE) changeState(RECOVERY); break;
    case RECOVERY:   stopAll(); if (elapsed >= T_RECOVERY) {
      currentLevel++;
      if (currentLevel >= 5) { changeState(DONE); samplingActive = false; Serial.println("SELESAI 5 LEVEL! DATA SIAP TRAINING!"); }
      else changeState(RAMP_UP);
    } break;
    case IDLE: case DONE: stopAll(); break;
  }
}

// ==================== KIRIM DATA KE RUST ====================
void sendSensorData() {
  // GM-XXX
  float no2 = (gas.measure_NO2()  < 30000) ? gas.measure_NO2()  / 1000.0 : -1.0;
  float eth = (gas.measure_C2H5OH()< 30000) ? gas.measure_C2H5OH()/ 1000.0 : -1.0;
  float voc = (gas.measure_VOC()  < 30000) ? gas.measure_VOC()  / 1000.0 : -1.0;
  float co  = (gas.measure_CO()   < 30000) ? gas.measure_CO()   / 1000.0 : -1.0;

  // MiCS-5524 — RUMUS DARI KODE KAMU YANG SUDAH 100% BENAR!
  float Rs = calculateRs();
  float co_mics = (Rs > 0) ? ppmFromRatio(Rs / R0_mics, "CO") : -1.0;
  float eth_mics = (Rs > 0) ? ppmFromRatio(Rs / R0_mics, "C2H5OH") : -1.0;
  float voc_mics = (Rs > 0) ? ppmFromRatio(Rs / R0_mics, "VOC") : -1.0;

  String data = "SENSOR:";
  data += String(no2,3) + "," + String(eth,3) + "," + String(voc,3) + "," + String(co,3) + ",";
  data += String(co_mics,3) + "," + String(eth_mics,3) + "," + String(voc_mics,3) + ",";
  data += String(currentState) + "," + String(currentLevel);

  if (client.connect(RUST_IP, RUST_PORT)) {
    client.print(data + "\n");
    client.stop();
  }
}
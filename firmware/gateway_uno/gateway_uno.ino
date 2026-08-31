/*
 * Gateway LoRa : Arduino Uno + RA-02 (SX1278 433 MHz)
 *
 * Reçoit les paquets capteur (14 octets, v1) et les paquets de poids (v2).
 * Mesure RSSI/SNR à la réception (puce SX1278), une ligne JSON sur USB.
 *
 * Commande PC (une ligne) : {"cmd":"start_round","round":1}
 * → émission LoRa start_round vers les nœuds.
 *
 * ATTENTION : RA-02 = 3.3 V. Convertisseur de niveaux obligatoire avec l'Uno 5 V.
 */

#include <SPI.h>
#include <LoRa.h>
#include <stdlib.h>
#include <string.h>
#include "fl_pkt.h"

#define LORA_SS            10
#define LORA_RST           9
#define LORA_DIO0          2

#define LORA_FREQ          433E6
#define LORA_SF            7
#define LORA_BW          125E3
#define LORA_CR            5
#define LORA_SYNC          0x12
#define LORA_TX_POWER      14

static void configureRadio() {
  LoRa.setSpreadingFactor(LORA_SF);
  LoRa.setSignalBandwidth(LORA_BW);
  LoRa.setCodingRate4(LORA_CR);
  LoRa.setTxPower(LORA_TX_POWER);
  LoRa.setSyncWord(LORA_SYNC);
  LoRa.enableCrc();
}

static void emitSensor(const uint8_t *buf, int n) {
  int rssi = LoRa.packetRssi();
  float snr = LoRa.packetSnr();

  if (n != PKT_SENSOR_LEN || buf[0] != PKT_MAGIC || buf[1] != PKT_VERSION_SENSOR) {
    Serial.print("{\"ok\":false,\"error\":\"bad_header\",\"len\":");
    Serial.print(n);
    Serial.print(",\"rssi\":");
    Serial.print(rssi);
    Serial.print(",\"snr\":");
    Serial.print(snr, 2);
    Serial.println("}");
    return;
  }

  bool ok = (pkt_xor8(buf, 13) == buf[13]);
  Serial.print("{\"type\":\"sensor\",\"node_id\":");
  Serial.print(buf[2]);
  Serial.print(",\"seq\":");
  Serial.print(pkt_get_u16(&buf[3]));
  Serial.print(",\"temp\":");
  Serial.print(pkt_get_i16(&buf[5]) / 10.0f, 1);
  Serial.print(",\"hum\":");
  Serial.print(pkt_get_u16(&buf[7]) / 10.0f, 1);
  Serial.print(",\"rssi\":");
  Serial.print(rssi);
  Serial.print(",\"snr\":");
  Serial.print(snr, 2);
  Serial.print(",\"uptime_s\":");
  Serial.print(pkt_get_u32(&buf[9]));
  Serial.print(",\"ok\":");
  Serial.print(ok ? "true" : "false");
  Serial.println("}");
}

static void emitWeights(const uint8_t *buf, int n) {
  int rssi = LoRa.packetRssi();
  float snr = LoRa.packetSnr();
  if (n != PKT_WEIGHTS_LEN || buf[0] != PKT_MAGIC || buf[1] != PKT_VERSION_FL
      || buf[2] != PKT_TYPE_WEIGHTS) {
    Serial.print("{\"ok\":false,\"error\":\"bad_header\",\"len\":");
    Serial.print(n);
    Serial.print(",\"rssi\":");
    Serial.print(rssi);
    Serial.print(",\"snr\":");
    Serial.print(snr, 2);
    Serial.println("}");
    return;
  }
  bool ok = (pkt_xor8(buf, 24) == buf[24]);
  Serial.print("{\"type\":\"weights\",\"node_id\":");
  Serial.print(buf[3]);
  Serial.print(",\"seq\":");
  Serial.print(pkt_get_u16(&buf[4]));
  Serial.print(",\"n_samples\":");
  Serial.print(pkt_get_u16(&buf[6]));
  Serial.print(",\"w\":[");
  Serial.print(pkt_get_i32(&buf[8]) / 1000000.0f, 6);
  Serial.print(",");
  Serial.print(pkt_get_i32(&buf[12]) / 1000000.0f, 6);
  Serial.print(",");
  Serial.print(pkt_get_i32(&buf[16]) / 1000000.0f, 6);
  Serial.print(",");
  Serial.print(pkt_get_i32(&buf[20]) / 1000000.0f, 6);
  Serial.print("],\"rssi\":");
  Serial.print(rssi);
  Serial.print(",\"snr\":");
  Serial.print(snr, 2);
  Serial.print(",\"ok\":");
  Serial.print(ok ? "true" : "false");
  Serial.println("}");
}

static void sendStartRound(uint16_t roundId) {
  uint8_t pkt[PKT_START_LEN];
  pkt[0] = PKT_MAGIC;
  pkt[1] = PKT_VERSION_FL;
  pkt[2] = PKT_TYPE_START;
  pkt[3] = 0;
  pkt_put_u16(&pkt[4], roundId);
  pkt[6] = 0;
  pkt[7] = pkt_xor8(pkt, 7);

  LoRa.beginPacket();
  LoRa.write(pkt, PKT_START_LEN);
  LoRa.endPacket();
  LoRa.receive();

  Serial.print("{\"type\":\"start_round_tx\",\"round\":");
  Serial.print(roundId);
  Serial.println("}");
}

static void pollSerialCmd() {
  static char line[48];
  static uint8_t len = 0;
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (len == 0) continue;
      line[len] = 0;
      len = 0;
      if (strstr(line, "start_round") == NULL) continue;
      uint16_t roundId = 1;
      char *p = strstr(line, "round");
      if (p) {
        while (*p && (*p < '0' || *p > '9')) p++;
        if (*p) roundId = (uint16_t)atoi(p);
      }
      sendStartRound(roundId);
    } else if (len < sizeof(line) - 1) {
      line[len++] = c;
    } else {
      len = 0;
    }
  }
}

void setup() {
  Serial.begin(115200);
  while (!Serial) { ; }

  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);
  if (!LoRa.begin(LORA_FREQ)) {
    Serial.println("{\"error\":\"lora_begin_failed\"}");
    while (1) delay(1000);
  }
  configureRadio();
  LoRa.receive();
  Serial.println("{\"status\":\"gateway_ready\",\"freq\":433,\"sf\":7,\"bw\":125,\"cr\":\"4/5\"}");
}

void loop() {
  pollSerialCmd();

  int packetSize = LoRa.parsePacket();
  if (packetSize <= 0) return;

  uint8_t buf[32];
  int n = 0;
  int cap = (int)sizeof(buf);
  while (LoRa.available() && n < cap) {
    buf[n++] = (uint8_t)LoRa.read();
  }
  while (LoRa.available()) LoRa.read();

  if (n >= 2 && buf[1] == PKT_VERSION_FL && n >= 3 && buf[2] == PKT_TYPE_WEIGHTS) {
    emitWeights(buf, n);
  } else {
    emitSensor(buf, n);
  }
}

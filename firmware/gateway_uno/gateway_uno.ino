/*
 * Gateway LoRa : Arduino Uno + RA-02 (SX1278 433 MHz)
 *
 * Reçoit les paquets capteur (14 octets) et les paquets de poids
 * (25 octets v2 ou 27 octets v3 avec round_id). RSSI/SNR à la réception.
 *
 * Commandes PC (une ligne) :
 *   {"cmd":"start_round","round":1}
 *   G <round> <w0> <w1> <w2> <w3>     (virgule fixe int32, 1e6)
 * → émission LoRa start_round (0x10) ou modèle global (0x30).
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

static unsigned long txQuietUntil = 0;

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
  bool v3 = (n == PKT_WEIGHTS_LEN);
  bool v2 = (n == PKT_WEIGHTS_LEN_V2);
  if ((!v3 && !v2) || buf[0] != PKT_MAGIC || buf[1] != PKT_VERSION_FL
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
  uint8_t xorOff = v3 ? 26 : 24;
  bool ok = (pkt_xor8(buf, xorOff) == buf[xorOff]);
  uint16_t roundId = v3 ? pkt_get_u16(&buf[24]) : 0;
  Serial.print("{\"type\":\"weights\",\"node_id\":");
  Serial.print(buf[3]);
  Serial.print(",\"seq\":");
  Serial.print(pkt_get_u16(&buf[4]));
  Serial.print(",\"n_samples\":");
  Serial.print(pkt_get_u16(&buf[6]));
  Serial.print(",\"round_id\":");
  Serial.print(roundId);
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
  delay(20);
  LoRa.receive();
  txQuietUntil = millis() + 80;

  Serial.print("{\"type\":\"start_round_tx\",\"round\":");
  Serial.print(roundId);
  Serial.println("}");
}

static void sendGlobal(uint16_t roundId, int32_t w0, int32_t w1, int32_t w2, int32_t w3) {
  uint8_t pkt[PKT_GLOBAL_LEN];
  pkt[0] = PKT_MAGIC;
  pkt[1] = PKT_VERSION_FL;
  pkt[2] = PKT_TYPE_GLOBAL;
  pkt[3] = 0;
  pkt_put_u16(&pkt[4], roundId);
  pkt[6] = 0;
  pkt[7] = 0;
  pkt_put_i32(&pkt[8], w0);
  pkt_put_i32(&pkt[12], w1);
  pkt_put_i32(&pkt[16], w2);
  pkt_put_i32(&pkt[20], w3);
  pkt[24] = pkt_xor8(pkt, 24);

  LoRa.beginPacket();
  LoRa.write(pkt, PKT_GLOBAL_LEN);
  LoRa.endPacket();
  delay(20);
  LoRa.receive();
  txQuietUntil = millis() + 80;

  Serial.print("{\"type\":\"global_tx\",\"round\":");
  Serial.print(roundId);
  Serial.println("}");
}

static int32_t nextI32(char **pp) {
  char *p = *pp;
  while (*p == ' ' || *p == '\t') p++;
  int32_t v = (int32_t)atol(p);
  if (*p == '-' || *p == '+') p++;
  while (*p >= '0' && *p <= '9') p++;
  *pp = p;
  return v;
}

static void pollSerialCmd() {
  static char line[96];
  static uint8_t len = 0;
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (len == 0) continue;
      line[len] = 0;
      len = 0;
      if (line[0] == 'G' && (line[1] == ' ' || line[1] == '\t')) {
        char *p = line + 1;
        while (*p == ' ' || *p == '\t') p++;
        uint16_t roundId = (uint16_t)atoi(p);
        if (*p == '-' || *p == '+') p++;
        while (*p >= '0' && *p <= '9') p++;
        int32_t w0 = nextI32(&p);
        int32_t w1 = nextI32(&p);
        int32_t w2 = nextI32(&p);
        int32_t w3 = nextI32(&p);
        sendGlobal(roundId, w0, w1, w2, w3);
        return;
      }
      if (strstr(line, "start_round") == NULL) continue;
      uint16_t roundId = 1;
      char *rp = strstr(line, "round");
      if (rp) {
        while (*rp && (*rp < '0' || *rp > '9')) rp++;
        if (*rp) roundId = (uint16_t)atoi(rp);
      }
      sendStartRound(roundId);
      return;
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
  if ((long)(millis() - txQuietUntil) < 0) return;

  int packetSize = LoRa.parsePacket();
  if (packetSize <= 0) return;

  uint8_t buf[32];
  int n = 0;
  int cap = (int)sizeof(buf);
  while (LoRa.available() && n < cap) {
    buf[n++] = (uint8_t)LoRa.read();
  }
  while (LoRa.available()) LoRa.read();

  if (n >= 3 && buf[1] == PKT_VERSION_FL && buf[2] == PKT_TYPE_WEIGHTS) {
    emitWeights(buf, n);
  } else if (n >= 3 && buf[1] == PKT_VERSION_FL
             && (buf[2] == PKT_TYPE_GLOBAL || buf[2] == PKT_TYPE_START)) {
    /* downlink echo : ignorer */
  } else if (n == PKT_SENSOR_LEN) {
    emitSensor(buf, n);
  }
}

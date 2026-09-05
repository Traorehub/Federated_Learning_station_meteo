/*
 * Nœud LoRa : ESP32 WROOM-32D + DHT11 + RA-02 (SX1278 433 MHz)
 *
 * Broches WROOM-32D (câblage respecté) :
 * NSS 5, SCK 18, MOSI 23, MISO 19, RST 14, DIO0 26
 *
 * Capture DHT toutes les 15 s (paquet v1, 14 octets).
 * Tampon local + SGD : prédire T[t] à partir de T[t-1], T[t-2], H[t-1].
 * Toutes les WEIGHT_EVERY mesures, envoi des 4 poids (27 octets, round_id).
 * Fenêtre RX 400 ms : start_round (0x10) et modèle global (0x30).
 *
 * TX labo 5 dBm (brownout). Pour 30-40 m indoor, préférer ce nœud
 * près de la gateway, ou tester 10 dBm si l'alim tient.
 *
 * Bibliothèques : LoRa (Sandeep Mistry), DHT sensor library (Adafruit).
 */

#include <math.h>
#include <SPI.h>
#include <LoRa.h>
#include <DHT.h>
#include "fl_pkt.h"
#include "fl_model.h"

#define NODE_ID            1
#define SEND_INTERVAL_MS   15000UL
#define WEIGHT_EVERY       4
#define RX_WINDOW_MS       400UL

#define DHTPIN             4
#define DHTTYPE            DHT11

#define LORA_SS            5
#define LORA_SCK           18
#define LORA_MOSI          23
#define LORA_MISO          19
#define LORA_RST           14
#define LORA_DIO0          26

#define LORA_FREQ          433E6
#define LORA_SF            7
#define LORA_BW            125E3
#define LORA_CR            5
#define LORA_TX_POWER      5
#define LORA_SYNC          0x12

DHT dht(DHTPIN, DHTTYPE);
FlModel model;
uint16_t seq = 0;
uint16_t roundId = 0;
uint8_t sinceWeights = 0;
unsigned long lastSend = 0;

static void configureRadio() {
  LoRa.setSpreadingFactor(LORA_SF);
  LoRa.setSignalBandwidth(LORA_BW);
  LoRa.setCodingRate4(LORA_CR);
  LoRa.setTxPower(LORA_TX_POWER);
  LoRa.setSyncWord(LORA_SYNC);
  LoRa.enableCrc();
}

static void sendSensor(float t, float h) {
  uint8_t pkt[PKT_SENSOR_LEN];
  pkt[0] = PKT_MAGIC;
  pkt[1] = PKT_VERSION_SENSOR;
  pkt[2] = (uint8_t)NODE_ID;
  pkt_put_u16(&pkt[3], seq);
  pkt_put_i16(&pkt[5], (int16_t)lroundf(t * 10.0f));
  pkt_put_u16(&pkt[7], (uint16_t)lroundf(h * 10.0f));
  pkt_put_u32(&pkt[9], millis() / 1000UL);
  pkt[13] = pkt_xor8(pkt, 13);

  LoRa.beginPacket();
  LoRa.write(pkt, PKT_SENSOR_LEN);
  LoRa.endPacket();
}

static void sendWeights() {
  uint8_t pkt[PKT_WEIGHTS_LEN];
  pkt[0] = PKT_MAGIC;
  pkt[1] = PKT_VERSION_FL;
  pkt[2] = PKT_TYPE_WEIGHTS;
  pkt[3] = (uint8_t)NODE_ID;
  pkt_put_u16(&pkt[4], seq);
  pkt_put_u16(&pkt[6], model.n_trained);
  pkt_put_i32(&pkt[8], fl_to_fixed(model.w[0]));
  pkt_put_i32(&pkt[12], fl_to_fixed(model.w[1]));
  pkt_put_i32(&pkt[16], fl_to_fixed(model.w[2]));
  pkt_put_i32(&pkt[20], fl_to_fixed(model.w[3]));
  pkt_put_u16(&pkt[24], roundId);
  pkt[26] = pkt_xor8(pkt, 26);

  LoRa.beginPacket();
  LoRa.write(pkt, PKT_WEIGHTS_LEN);
  LoRa.endPacket();

  Serial.print("TX weights id=");
  Serial.print(NODE_ID);
  Serial.print(" round=");
  Serial.print(roundId);
  Serial.print(" n=");
  Serial.print(model.n_trained);
  Serial.print(" w=");
  Serial.print(model.w[0], 4);
  Serial.print(",");
  Serial.print(model.w[1], 4);
  Serial.print(",");
  Serial.print(model.w[2], 4);
  Serial.print(",");
  Serial.println(model.w[3], 4);
}

static void pollDownlink() {
  int n = LoRa.parsePacket();
  if (n < PKT_START_LEN) return;
  uint8_t buf[PKT_WEIGHTS_LEN];
  int cap = n < (int)sizeof(buf) ? n : (int)sizeof(buf);
  int got = 0;
  while (LoRa.available() && got < cap) {
    buf[got++] = (uint8_t)LoRa.read();
  }
  while (LoRa.available()) LoRa.read();
  if (got < PKT_START_LEN) return;
  if (buf[0] != PKT_MAGIC || buf[1] != PKT_VERSION_FL) return;

  if (buf[2] == PKT_TYPE_START && got == PKT_START_LEN) {
    if (pkt_xor8(buf, 7) != buf[7]) return;
    roundId = pkt_get_u16(&buf[4]);
    Serial.print("RX start_round ");
    Serial.println(roundId);
    fl_train(&model);
    sendWeights();
    LoRa.receive();
  } else if (buf[2] == PKT_TYPE_GLOBAL && got == PKT_GLOBAL_LEN) {
    if (pkt_xor8(buf, 24) != buf[24]) return;
    roundId = pkt_get_u16(&buf[4]);
    fl_apply_w(
      &model,
      fl_from_fixed(pkt_get_i32(&buf[8])),
      fl_from_fixed(pkt_get_i32(&buf[12])),
      fl_from_fixed(pkt_get_i32(&buf[16])),
      fl_from_fixed(pkt_get_i32(&buf[20]))
    );
    Serial.print("RX global round=");
    Serial.print(roundId);
    Serial.print(" w=");
    Serial.print(model.w[0], 4);
    Serial.print(",");
    Serial.print(model.w[1], 4);
    Serial.print(",");
    Serial.print(model.w[2], 4);
    Serial.print(",");
    Serial.println(model.w[3], 4);
  }
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("FL node WROOM-32D boot");
  Serial.print("id=");
  Serial.println(NODE_ID);
  Serial.flush();
  delay(2000);

  dht.begin();
  fl_init(&model);

  SPI.begin(LORA_SCK, LORA_MISO, LORA_MOSI, LORA_SS);
  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);
  Serial.println("LoRa begin...");
  Serial.flush();
  if (!LoRa.begin(LORA_FREQ)) {
    Serial.println("LoRa begin FAILED");
    while (1) delay(1000);
  }
  configureRadio();
  Serial.println("LoRa OK 433MHz SF7 BW125 CR4/5 TXdbm=5");
  Serial.flush();
  LoRa.receive();
}

void loop() {
  pollDownlink();

  unsigned long now = millis();
  if (now - lastSend < SEND_INTERVAL_MS) return;
  lastSend = now;

  float t = dht.readTemperature();
  float h = dht.readHumidity();
  if (isnan(t) || isnan(h)) {
    Serial.println("DHT read failed, skip");
    LoRa.receive();
    return;
  }

  fl_push(&model, t, h);
  fl_train(&model);
  sendSensor(t, h);

  Serial.print("TX id=");
  Serial.print(NODE_ID);
  Serial.print(" seq=");
  Serial.print(seq);
  Serial.print(" t=");
  Serial.print(t, 1);
  Serial.print(" h=");
  Serial.println(h, 1);

  seq++;
  sinceWeights++;
  if (sinceWeights >= WEIGHT_EVERY && model.n >= 3) {
    delay(200U * NODE_ID);
    sendWeights();
    sinceWeights = 0;
  }

  LoRa.receive();
}

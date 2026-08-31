/*
 * Nœud LoRa : ESP32-S3 + DHT11 + RA-02 (SX1278 433 MHz)
 *
 * Broches S3 (câblage réel LoRa) :
 * NSS 5, SCK 18, MOSI 6, MISO 16, RST 14, DIO0 15
 *
 * DHT : capteur déjà soudé sur la carte d'extension, DATA GPIO 2.
 * SPI.begin(18, 16, 6, 5) obligatoire avant LoRa.begin.
 *
 * Capture 15 s (paquet v1) + tampon local + SGD + paquets de poids (v2).
 * TX 14 dBm : mieux placé comme nœud éloigné (30-40 m) que le WROOM à 5 dBm.
 *
 * Bibliothèques : LoRa (Sandeep Mistry), DHT sensor library (Adafruit).
 */

#include <math.h>
#include <SPI.h>
#include <LoRa.h>
#include <DHT.h>
#include "fl_pkt.h"
#include "fl_model.h"

#define NODE_ID            2
#define SEND_INTERVAL_MS   15000UL
#define WEIGHT_EVERY       4
#define RX_WINDOW_MS       400UL

#define DHTPIN             2
#define DHTTYPE            DHT11

#define LORA_SS            5
#define LORA_SCK           18
#define LORA_MOSI          6
#define LORA_MISO          16
#define LORA_RST           14
#define LORA_DIO0          15

#define LORA_FREQ          433E6
#define LORA_SF            7
#define LORA_BW            125E3
#define LORA_CR            5
#define LORA_TX_POWER      14
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
  pkt[24] = pkt_xor8(pkt, 24);

  LoRa.beginPacket();
  LoRa.write(pkt, PKT_WEIGHTS_LEN);
  LoRa.endPacket();

  Serial.print("TX weights id=");
  Serial.print(NODE_ID);
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

static void listenDownlink() {
  LoRa.receive();
  unsigned long t0 = millis();
  while (millis() - t0 < RX_WINDOW_MS) {
    int n = LoRa.parsePacket();
    if (n < PKT_START_LEN) continue;
    uint8_t buf[PKT_START_LEN];
    int got = 0;
    while (LoRa.available() && got < PKT_START_LEN) {
      buf[got++] = (uint8_t)LoRa.read();
    }
    while (LoRa.available()) LoRa.read();
    if (got != PKT_START_LEN) continue;
    if (buf[0] != PKT_MAGIC || buf[1] != PKT_VERSION_FL || buf[2] != PKT_TYPE_START) {
      continue;
    }
    if (pkt_xor8(buf, 7) != buf[7]) continue;
    roundId = pkt_get_u16(&buf[4]);
    Serial.print("RX start_round ");
    Serial.println(roundId);
    fl_train(&model);
    sendWeights();
  }
}

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.print("FL node ESP32-S3 ");
  Serial.println(NODE_ID);

  dht.begin();
  fl_init(&model);

  SPI.begin(LORA_SCK, LORA_MISO, LORA_MOSI, LORA_SS);
  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);
  if (!LoRa.begin(LORA_FREQ)) {
    Serial.println("LoRa begin FAILED");
    while (1) delay(1000);
  }
  configureRadio();
  Serial.println("LoRa OK 433MHz SF7 BW125 CR4/5 TXdbm=14");
}

void loop() {
  unsigned long now = millis();
  if (now - lastSend < SEND_INTERVAL_MS) return;
  lastSend = now;

  float t = dht.readTemperature();
  float h = dht.readHumidity();
  if (isnan(t) || isnan(h)) {
    Serial.println("DHT read failed, skip");
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

  listenDownlink();
}

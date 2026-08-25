/*
 * Nœud LoRa : ESP32-S3 + DHT11 + RA-02 (SX1278 433 MHz)
 *
 * Broches S3 (câblage réel LoRa) :
 * NSS 5, SCK 18, MOSI 6, MISO 16, RST 14, DIO0 15
 *
 * DHT : capteur déjà soudé sur la carte d'extension, pas un 2e module.
 * DATA souvent GPIO 2 (cavalier à côté du DHT). Confirmer avec
 * firmware/test_dht_s3 avant de compter dessus.
 *
 * WROOM-32D : firmware/node_esp32
 *
 * Un envoi toutes les SEND_INTERVAL_MS, indépendamment de tout entraînement.
 * Changer NODE_ID avant de flasher.
 *
 * Bibliothèques : LoRa (Sandeep Mistry), DHT sensor library (Adafruit).
 */

#include <math.h>
#include <SPI.h>
#include <LoRa.h>
#include <DHT.h>

#define NODE_ID            2
#define SEND_INTERVAL_MS   15000UL

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
#define LORA_CR            5          /* 4/5 */
#define LORA_TX_POWER      14
#define LORA_SYNC          0x12

#define PKT_MAGIC          0xA5
#define PKT_VERSION        0x01
#define PKT_LEN            14

DHT dht(DHTPIN, DHTTYPE);

uint16_t seq = 0;
unsigned long lastSend = 0;

static uint8_t xor8(const uint8_t *d, size_t n) {
  uint8_t x = 0;
  for (size_t i = 0; i < n; i++) x ^= d[i];
  return x;
}

static void putU16(uint8_t *p, uint16_t v) {
  p[0] = (uint8_t)(v & 0xFF);
  p[1] = (uint8_t)((v >> 8) & 0xFF);
}

static void putI16(uint8_t *p, int16_t v) {
  putU16(p, (uint16_t)v);
}

static void putU32(uint8_t *p, uint32_t v) {
  p[0] = (uint8_t)(v & 0xFF);
  p[1] = (uint8_t)((v >> 8) & 0xFF);
  p[2] = (uint8_t)((v >> 16) & 0xFF);
  p[3] = (uint8_t)((v >> 24) & 0xFF);
}

static void configureRadio() {
  LoRa.setSpreadingFactor(LORA_SF);
  LoRa.setSignalBandwidth(LORA_BW);
  LoRa.setCodingRate4(LORA_CR);
  LoRa.setTxPower(LORA_TX_POWER);
  LoRa.setSyncWord(LORA_SYNC);
  LoRa.enableCrc();
}

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.print("FL node ESP32-S3 ");
  Serial.println(NODE_ID);

  dht.begin();

  SPI.begin(LORA_SCK, LORA_MISO, LORA_MOSI, LORA_SS);
  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);
  if (!LoRa.begin(LORA_FREQ)) {
    Serial.println("LoRa begin FAILED");
    while (1) delay(1000);
  }
  configureRadio();
  Serial.println("LoRa OK 433MHz SF7 BW125 CR4/5");
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

  uint8_t pkt[PKT_LEN];
  pkt[0] = PKT_MAGIC;
  pkt[1] = PKT_VERSION;
  pkt[2] = (uint8_t)NODE_ID;
  putU16(&pkt[3], seq);
  putI16(&pkt[5], (int16_t)lroundf(t * 10.0f));
  putU16(&pkt[7], (uint16_t)lroundf(h * 10.0f));
  putU32(&pkt[9], millis() / 1000UL);
  pkt[13] = xor8(pkt, 13);

  LoRa.beginPacket();
  LoRa.write(pkt, PKT_LEN);
  LoRa.endPacket();

  Serial.print("TX id=");
  Serial.print(NODE_ID);
  Serial.print(" seq=");
  Serial.print(seq);
  Serial.print(" t=");
  Serial.print(t, 1);
  Serial.print(" h=");
  Serial.println(h, 1);

  seq++;
}

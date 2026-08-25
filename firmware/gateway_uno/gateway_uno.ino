/*
 * Gateway LoRa : Arduino Uno + RA-02 (SX1278 433 MHz)
 *
 * Reçoit les paquets 14 octets, mesure RSSI/SNR, émet une ligne JSON sur USB.
 * L'agent PC (serial_bridge.py) lit ce flux et POST vers le VPS.
 *
 * ATTENTION : RA-02 = 3.3 V. Convertisseur de niveaux obligatoire avec l'Uno 5 V.
 */

#include <SPI.h>
#include <LoRa.h>

#define LORA_SS            10
#define LORA_RST           9
#define LORA_DIO0          2

#define LORA_FREQ          433E6
#define LORA_SF            7
#define LORA_BW            125E3
#define LORA_CR            5
#define LORA_SYNC          0x12

#define PKT_MAGIC          0xA5
#define PKT_VERSION        0x01
#define PKT_LEN            14

static uint8_t xor8(const uint8_t *d, size_t n) {
  uint8_t x = 0;
  for (size_t i = 0; i < n; i++) x ^= d[i];
  return x;
}

static uint16_t getU16(const uint8_t *p) {
  return (uint16_t)p[0] | ((uint16_t)p[1] << 8);
}

static int16_t getI16(const uint8_t *p) {
  return (int16_t)getU16(p);
}

static uint32_t getU32(const uint8_t *p) {
  return (uint32_t)p[0]
       | ((uint32_t)p[1] << 8)
       | ((uint32_t)p[2] << 16)
       | ((uint32_t)p[3] << 24);
}

static void configureRadio() {
  LoRa.setSpreadingFactor(LORA_SF);
  LoRa.setSignalBandwidth(LORA_BW);
  LoRa.setCodingRate4(LORA_CR);
  LoRa.setSyncWord(LORA_SYNC);
  LoRa.enableCrc();
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
  Serial.println("{\"status\":\"gateway_ready\",\"freq\":433,\"sf\":7,\"bw\":125,\"cr\":\"4/5\"}");
}

void loop() {
  int packetSize = LoRa.parsePacket();
  if (packetSize <= 0) return;

  uint8_t buf[PKT_LEN];
  int n = 0;
  while (LoRa.available() && n < PKT_LEN) {
    buf[n++] = (uint8_t)LoRa.read();
  }
  while (LoRa.available()) LoRa.read();

  int rssi = LoRa.packetRssi();
  float snr = LoRa.packetSnr();

  if (n != PKT_LEN || buf[0] != PKT_MAGIC || buf[1] != PKT_VERSION) {
    Serial.print("{\"ok\":false,\"error\":\"bad_header\",\"len\":");
    Serial.print(n);
    Serial.print(",\"rssi\":");
    Serial.print(rssi);
    Serial.print(",\"snr\":");
    Serial.print(snr, 2);
    Serial.println("}");
    return;
  }

  bool ok = (xor8(buf, 13) == buf[13]);
  uint8_t nodeId = buf[2];
  uint16_t seq = getU16(&buf[3]);
  float temp = getI16(&buf[5]) / 10.0f;
  float hum = getU16(&buf[7]) / 10.0f;
  uint32_t uptime = getU32(&buf[9]);

  Serial.print("{\"node_id\":");
  Serial.print(nodeId);
  Serial.print(",\"seq\":");
  Serial.print(seq);
  Serial.print(",\"temp\":");
  Serial.print(temp, 1);
  Serial.print(",\"hum\":");
  Serial.print(hum, 1);
  Serial.print(",\"rssi\":");
  Serial.print(rssi);
  Serial.print(",\"snr\":");
  Serial.print(snr, 2);
  Serial.print(",\"uptime_s\":");
  Serial.print(uptime);
  Serial.print(",\"ok\":");
  Serial.print(ok ? "true" : "false");
  Serial.println("}");
}

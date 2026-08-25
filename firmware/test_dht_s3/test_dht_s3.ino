/*
 * Test DHT embarqué (ESP32-S3 + carte d'extension).
 *
 * Pas de LoRa. Ouvre le Moniteur série à 115200.
 * Si une ligne "OK GPIO x" apparaît avec temp/humidité, le capteur marche
 * et c'est cette broche qu'on mettra dans node_esp32_s3.ino (DHTPIN).
 *
 * Sur beaucoup de cartes d'extension S3 : DHT = GPIO 2 + un cavalier
 * à côté du capteur. Sans cavalier, lecture échoue.
 *
 * Bibliothèques : DHT sensor library (Adafruit) + Adafruit Unified Sensor.
 */

#include <DHT.h>

#define DHTTYPE DHT11

static const int CANDIDATES[] = {2, 4, 36, 1, 21, 13, 20, 3, 7, 8, 9, 10};
static const int N = sizeof(CANDIDATES) / sizeof(CANDIDATES[0]);

void setup() {
  Serial.begin(115200);
  delay(1500);
  Serial.println("Scan DHT11 sur GPIO candidats...");
  Serial.println("Si tout echoue : verifier le cavalier a cote du DHT.");
}

void loop() {
  for (int i = 0; i < N; i++) {
    int pin = CANDIDATES[i];
    DHT dht(pin, DHTTYPE);
    dht.begin();
    delay(1500);
    float t = dht.readTemperature();
    float h = dht.readHumidity();
    Serial.print("GPIO ");
    Serial.print(pin);
    Serial.print(" : ");
    if (isnan(t) || isnan(h)) {
      Serial.println("pas de reponse");
    } else {
      Serial.print("OK  T=");
      Serial.print(t, 1);
      Serial.print(" C  H=");
      Serial.print(h, 1);
      Serial.println(" %");
    }
  }
  Serial.println("---");
  delay(2000);
}

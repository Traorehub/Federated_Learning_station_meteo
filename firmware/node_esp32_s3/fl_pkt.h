#ifndef FL_PKT_H
#define FL_PKT_H

#include <stddef.h>
#include <stdint.h>

#define PKT_MAGIC          0xA5
#define PKT_VERSION_SENSOR 0x01
#define PKT_VERSION_FL     0x02
#define PKT_TYPE_START     0x10
#define PKT_TYPE_WEIGHTS   0x20
#define PKT_SENSOR_LEN     14
#define PKT_WEIGHTS_LEN    25
#define PKT_START_LEN      8

static uint8_t pkt_xor8(const uint8_t *d, size_t n) {
  uint8_t x = 0;
  for (size_t i = 0; i < n; i++) x ^= d[i];
  return x;
}

static void pkt_put_u16(uint8_t *p, uint16_t v) {
  p[0] = (uint8_t)(v & 0xFF);
  p[1] = (uint8_t)((v >> 8) & 0xFF);
}

static uint16_t pkt_get_u16(const uint8_t *p) {
  return (uint16_t)p[0] | ((uint16_t)p[1] << 8);
}

static void pkt_put_i16(uint8_t *p, int16_t v) {
  pkt_put_u16(p, (uint16_t)v);
}

static int16_t pkt_get_i16(const uint8_t *p) {
  return (int16_t)pkt_get_u16(p);
}

static void pkt_put_u32(uint8_t *p, uint32_t v) {
  p[0] = (uint8_t)(v & 0xFF);
  p[1] = (uint8_t)((v >> 8) & 0xFF);
  p[2] = (uint8_t)((v >> 16) & 0xFF);
  p[3] = (uint8_t)((v >> 24) & 0xFF);
}

static uint32_t pkt_get_u32(const uint8_t *p) {
  return (uint32_t)p[0]
       | ((uint32_t)p[1] << 8)
       | ((uint32_t)p[2] << 16)
       | ((uint32_t)p[3] << 24);
}

static void pkt_put_i32(uint8_t *p, int32_t v) {
  pkt_put_u32(p, (uint32_t)v);
}

static int32_t pkt_get_i32(const uint8_t *p) {
  return (int32_t)pkt_get_u32(p);
}

#endif

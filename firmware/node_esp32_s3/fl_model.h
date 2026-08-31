/*
 * Modèle prédictif minuscule (v2) : estimer T[t] à partir de T[t-1], T[t-2], H[t-1].
 * Entraînement local (SGD). Les poids partent ensuite en LoRa, pas les mesures brutes.
 *
 * Entrées normalisées (T/50, H/100) pour garder des coefficients stables sur ESP32.
 */

#ifndef FL_MODEL_H
#define FL_MODEL_H

#include <math.h>
#include <stdint.h>

#define FL_BUF     32
#define FL_N_W     4
#define FL_EPOCHS  8
#define FL_LR      0.05f
#define FL_FIXED   1000000.0f

struct FlSample {
  float t;
  float h;
};

struct FlModel {
  FlSample buf[FL_BUF];
  uint8_t n;
  uint8_t head;
  float w[FL_N_W];
  uint16_t n_trained;
};

static FlSample fl_at(const FlModel *m, int i) {
  uint8_t oldest = (uint8_t)((m->head + FL_BUF - m->n) % FL_BUF);
  return m->buf[(oldest + i) % FL_BUF];
}

static float fl_nt(float t) { return t / 50.0f; }
static float fl_nh(float h) { return h / 100.0f; }

static void fl_init(FlModel *m) {
  m->n = 0;
  m->head = 0;
  m->n_trained = 0;
  m->w[0] = 0.6f;
  m->w[1] = 0.3f;
  m->w[2] = 0.0f;
  m->w[3] = 0.0f;
}

static void fl_push(FlModel *m, float t, float h) {
  m->buf[m->head].t = t;
  m->buf[m->head].h = h;
  m->head = (uint8_t)((m->head + 1) % FL_BUF);
  if (m->n < FL_BUF) m->n++;
}

static float fl_predict_norm(const FlModel *m, float t1, float t2, float h1) {
  return m->w[0] * fl_nt(t1) + m->w[1] * fl_nt(t2) + m->w[2] * fl_nh(h1) + m->w[3];
}

static void fl_train(FlModel *m) {
  if (m->n < 3) return;
  for (int e = 0; e < FL_EPOCHS; e++) {
    for (int i = 2; i < m->n; i++) {
      FlSample s0 = fl_at(m, i);
      FlSample s1 = fl_at(m, i - 1);
      FlSample s2 = fl_at(m, i - 2);
      float x0 = fl_nt(s1.t);
      float x1 = fl_nt(s2.t);
      float x2 = fl_nh(s1.h);
      float y = fl_nt(s0.t);
      float yhat = m->w[0] * x0 + m->w[1] * x1 + m->w[2] * x2 + m->w[3];
      float err = yhat - y;
      m->w[0] -= FL_LR * err * x0;
      m->w[1] -= FL_LR * err * x1;
      m->w[2] -= FL_LR * err * x2;
      m->w[3] -= FL_LR * err;
    }
  }
  m->n_trained = (uint16_t)m->n;
}

static int32_t fl_to_fixed(float x) {
  return (int32_t)lroundf(x * FL_FIXED);
}

#endif

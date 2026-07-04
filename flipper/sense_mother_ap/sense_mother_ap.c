/**
 * Sense Mother AP — Flipper Zero prototype.
 *
 * Phase 1: RX-only. Configure CC1101 for the sen.se SimpliciTI PHY
 * (915 MHz, 100 kbps 2-GFSK, sync 0xD391, PN9 whitening), receive
 * variable-length packets, dewhiten (hardware-assisted), parse
 * SimpliciTI framing, and dump the fields to the debug log.
 *
 * On screen we render a one-shot dashboard: frame count, last SRCADDR,
 * last PORT, and RSSI. No settings UI yet — everything is compile-time.
 */

#include <furi.h>
#include <furi_hal.h>
#include <gui/gui.h>
#include <gui/view_port.h>
#include <input/input.h>
#include <cli/cli.h>
#include <toolbox/cli/cli_command.h>
#include <string.h>

// RECORD_INPUT_EVENTS is defined in input/input.h — this is the raw
// FuriPubSub used for both hardware and CLI-injected input events.
// GUI service subscribes to this record too, but its dispatcher filters
// CLI events (they lack a matching Press→Release sequence). By
// subscribing directly we skip that filter — the CLI `input send up short`
// command reaches us, which lets us drive the app from a script without
// touching the D-pad.

#include "cc1101_preset.h"
#include "pn9.h"
#include "frame_parse.h"

#define TAG "SenseMotherAP"

#define SENSE_FREQ_US 915000000u
#define SENSE_FREQ_EU 868350000u
// Change here for a EU (868) unit. Left as compile-time until we add a UI toggle.
#define SENSE_FREQ    SENSE_FREQ_US

// ── CC1101 SPI helpers ──────────────────────────────────────────────
//
// Third-party FAPs generally reach the CC1101 through the stable
// furi_hal_spi API + the subghz bus handle, rather than the internal
// lib/drivers/cc1101.h (which is not always in the public SDK). These
// helpers only touch bytes on the wire; furi_hal_subghz still owns the
// radio state machine transitions.
//
// CC1101 command byte:  [READ][BURST][A5 A4 A3 A2 A1 A0]

#define CC1101_READ_BIT   0x80
#define CC1101_BURST_BIT  0x40

#define CC1101_STROBE_SRES  0x30
#define CC1101_STROBE_SRX   0x34
#define CC1101_STROBE_STX   0x35
#define CC1101_STROBE_SIDLE 0x36
#define CC1101_STROBE_SFRX  0x3A
#define CC1101_STROBE_SFTX  0x3B
#define CC1101_STROBE_SNOP  0x3D

#define CC1101_STATUS_RXBYTES   0x3B
#define CC1101_STATUS_TXBYTES   0x3A
#define CC1101_STATUS_PKTSTATUS 0x38
#define CC1101_STATUS_MARCSTATE 0x35
#define CC1101_STATUS_RSSI      0x34

#define CC1101_FIFO  0x3F

static uint8_t cc1101_strobe(uint8_t strobe) {
    uint8_t status = 0;
    furi_hal_spi_acquire(&furi_hal_spi_bus_handle_subghz);
    furi_hal_spi_bus_trx(&furi_hal_spi_bus_handle_subghz, &strobe, &status, 1, 100);
    furi_hal_spi_release(&furi_hal_spi_bus_handle_subghz);
    return status;
}

static uint8_t cc1101_read_status_reg(uint8_t reg) {
    // Status registers require the BURST bit to distinguish from strobes
    uint8_t tx[2] = {(uint8_t)(reg | CC1101_READ_BIT | CC1101_BURST_BIT), 0};
    uint8_t rx[2] = {0, 0};
    furi_hal_spi_acquire(&furi_hal_spi_bus_handle_subghz);
    furi_hal_spi_bus_trx(&furi_hal_spi_bus_handle_subghz, tx, rx, 2, 100);
    furi_hal_spi_release(&furi_hal_spi_bus_handle_subghz);
    return rx[1];
}

// Config registers (0x00-0x2F): READ bit only (BURST bit turns them into a
// burst read across many regs).
static uint8_t cc1101_read_config_reg(uint8_t reg) {
    uint8_t tx[2] = {(uint8_t)(reg | CC1101_READ_BIT), 0};
    uint8_t rx[2] = {0, 0};
    furi_hal_spi_acquire(&furi_hal_spi_bus_handle_subghz);
    furi_hal_spi_bus_trx(&furi_hal_spi_bus_handle_subghz, tx, rx, 2, 100);
    furi_hal_spi_release(&furi_hal_spi_bus_handle_subghz);
    return rx[1];
}

static void cc1101_read_fifo(uint8_t* dst, size_t len) {
    if(len == 0) return;
    uint8_t addr = CC1101_FIFO | CC1101_READ_BIT | CC1101_BURST_BIT;
    furi_hal_spi_acquire(&furi_hal_spi_bus_handle_subghz);
    furi_hal_spi_bus_tx(&furi_hal_spi_bus_handle_subghz, &addr, 1, 100);
    furi_hal_spi_bus_rx(&furi_hal_spi_bus_handle_subghz, dst, len, 100);
    furi_hal_spi_release(&furi_hal_spi_bus_handle_subghz);
}

static void cc1101_write_fifo(const uint8_t* src, size_t len) {
    if(len == 0) return;
    uint8_t addr = CC1101_FIFO | CC1101_BURST_BIT;
    furi_hal_spi_acquire(&furi_hal_spi_bus_handle_subghz);
    furi_hal_spi_bus_tx(&furi_hal_spi_bus_handle_subghz, &addr, 1, 100);
    furi_hal_spi_bus_tx(&furi_hal_spi_bus_handle_subghz, src, len, 100);
    furi_hal_spi_release(&furi_hal_spi_bus_handle_subghz);
}

// Single-byte register write (no burst bit). Used for the FIFO LEN byte in
// packet-mode TX — stock furi_hal_subghz_write_packet does it this way.
static void cc1101_write_single_reg(uint8_t reg, uint8_t val) {
    uint8_t tx[2] = {reg, val};
    uint8_t rx[2] = {0, 0};
    furi_hal_spi_acquire(&furi_hal_spi_bus_handle_subghz);
    furi_hal_spi_bus_trx(&furi_hal_spi_bus_handle_subghz, tx, rx, 2, 100);
    furi_hal_spi_release(&furi_hal_spi_bus_handle_subghz);
}

// CC1101 RSSI decode (datasheet §17.3): signed offset + fixed -74 offset.
static int cc1101_decode_rssi(uint8_t raw) {
    int r = raw >= 128 ? (int)raw - 256 : (int)raw;
    return (r / 2) - 74;
}

// ── SimpliciTI Join reply ───────────────────────────────────────────
//
// Full protocol writeup in JOIN.md. Short version:
//   Cookie broadcasts port-3 with app payload:
//     [prefix][REQ=0x01][TID][Token=08 07 06 05][NumConn][ProtoVer]
//   AP replies unicast port-3 with (TI stock 7-byte body):
//     [REQ|REPLY=0x81][TID echo][LinkToken(4)][CryptKeySize=0]

// AP address printed in-repo. `DE AD BE EF` — easy to spot in captures,
// doesn't collide with any real Mother address the SDR has seen.
static const uint8_t AP_ADDR[4] = {0xDE, 0xAD, 0xBE, 0xEF};
// LinkToken: arbitrary opaque 4 bytes. TI's ref uses 0xDEADBEEF too.
static const uint8_t LINK_TOKEN[4] = {0xDE, 0xAD, 0xBE, 0xEF};

// Build the reply frame (LEN byte then body). Returns total bytes written.
static size_t build_join_reply(uint8_t* out, const uint8_t* cookie_addr, uint8_t tid) {
    // body = DST(4) + SRC(4) + PORT(1) + DEVINFO(1) + app(7) = 17
    out[0] = 17; // LEN — counts bytes after LEN, excluding CC1101-appended CRC
    memcpy(&out[1], cookie_addr, 4); // DSTADDR = Cookie's SRC
    memcpy(&out[5], AP_ADDR, 4);     // SRCADDR = our AP address
    out[9] = 0x03;                   // PORT = SMPL_PORT_JOIN
    out[10] = 0x20;                  // DEVINFO: sender=AP (bits 5:4 = 10), hop=0
    out[11] = 0x81;                  // REQ_JOIN | NWK_APP_REPLY_BIT
    out[12] = tid;                   // echo Cookie's TID
    memcpy(&out[13], LINK_TOKEN, 4);
    out[17] = 0x00;                  // CryptKeySize = 0 (no encryption)
    return 18;
}

// Send a preformed frame via CC1101 packet-mode TX. The CC1101 auto-adds
// PN9 whitening (WHITE_DATA=1) and CCITT CRC (CRC_EN=1) per our preset.
//
// State-machine handling is delegated to furi_hal_subghz_idle / _tx so we
// get their internal wait-for-state furi_check semantics — the raw SIDLE
// strobe path made a previous version reach STX before CC1101 had settled
// in IDLE, and `furi_check(cc1101_wait_status_state(..., CC1101StateTX, 10000))`
// inside furi_hal_subghz_tx tripped and rebooted the Flipper.
static bool cc1101_tx_packet(const uint8_t* frame, size_t len) {
    furi_hal_subghz_idle();
    cc1101_strobe(CC1101_STROBE_SFTX);
    // Replicate stock furi_hal_subghz_write_packet: LEN via a single-byte
    // register-style write, then body via burst. The diagnostic pad test
    // showed CC1101 was NOT stopping at LEN when we did LEN + body as one
    // burst; splitting might land the write into the FIFO in a way the
    // packet-length hardware picks up.
    uint8_t len_byte = frame[0];
    cc1101_write_single_reg(CC1101_FIFO, len_byte);
    if(len > 1) cc1101_write_fifo(&frame[1], len - 1);

    if(!furi_hal_subghz_tx()) {
        FURI_LOG_E(TAG, "furi_hal_subghz_tx() denied by regulation");
        return false;
    }

    // Snapshot MARCSTATE + TXBYTES immediately after TX starts. If the chip
    // really is transmitting, MARCSTATE should be 0x13 (TX) briefly then 0x14
    // (TX_END) then 0x01 (IDLE); TXBYTES should drain from 18 → 0. If the PA
    // is silently gated we'd see MARCSTATE stuck or TXBYTES not draining.
    uint8_t marc_start = cc1101_read_status_reg(CC1101_STATUS_MARCSTATE) & 0x1F;
    uint8_t txb_start = cc1101_read_status_reg(CC1101_STATUS_TXBYTES) & 0x7F;

    // Transmission is autonomous once we're in TX. Sample MARCSTATE at three
    // moments so we can tell "still transmitting" (13/14) from "clean IDLE"
    // (01) from "underflowed mid-packet" (16). At 100 kbps, 20 on-air bytes
    // finish in ~1.8 ms, so 5 ms mid, 50 ms late.
    furi_delay_ms(5);
    uint8_t marc_mid = cc1101_read_status_reg(CC1101_STATUS_MARCSTATE) & 0x1F;
    uint8_t txb_mid = cc1101_read_status_reg(CC1101_STATUS_TXBYTES) & 0x7F;

    furi_delay_ms(45);
    uint8_t marc_end = cc1101_read_status_reg(CC1101_STATUS_MARCSTATE) & 0x1F;
    uint8_t txb_end = cc1101_read_status_reg(CC1101_STATUS_TXBYTES) & 0x7F;
    FURI_LOG_I(
        TAG,
        "tx: MARCSTATE %02x@0 → %02x@5ms → %02x@50ms  TXBYTES %u/%u/%u",
        marc_start,
        marc_mid,
        marc_end,
        txb_start,
        txb_mid,
        txb_end);

    furi_hal_subghz_idle();
    return true;
}

// ── UI state ────────────────────────────────────────────────────────

typedef struct {
    FuriMutex* mutex;
    uint32_t frame_count;
    uint32_t bad_count;
    uint32_t join_rx_count;  // Cookie Join broadcasts seen
    uint32_t join_tx_count;  // Join replies we've sent
    uint8_t last_src[4];
    uint8_t last_port;
    int last_rssi;
    bool last_join;
    bool running;
} AppState;

typedef struct {
    AppState* state;
    FuriMessageQueue* input_queue;
    FuriThread* rx_thread;
    // When set, the RX worker fires one test TX at the next loop iteration
    // instead of waiting for a Cookie Join. Cleared by the worker after it
    // fires so the button press behaves as a one-shot.
    volatile bool test_tx_pending;
    FuriPubSub* input_events;
    FuriPubSubSubscription* input_sub;
} App;

// ── Render ──────────────────────────────────────────────────────────

static void render_cb(Canvas* c, void* ctx) {
    App* app = ctx;
    furi_mutex_acquire(app->state->mutex, FuriWaitForever);
    AppState s = *app->state;
    furi_mutex_release(app->state->mutex);

    canvas_clear(c);
    canvas_set_font(c, FontPrimary);
    canvas_draw_str(c, 2, 10, "Sense Mother AP");

    char buf[48];
    canvas_set_font(c, FontSecondary);
    snprintf(buf, sizeof(buf), "RX: %lu  bad: %lu", s.frame_count, s.bad_count);
    canvas_draw_str(c, 2, 24, buf);

    if(s.frame_count > 0) {
        snprintf(
            buf,
            sizeof(buf),
            "src %02x%02x%02x%02x p%u %s",
            s.last_src[0],
            s.last_src[1],
            s.last_src[2],
            s.last_src[3],
            s.last_port,
            s.last_join ? "JOIN" : "");
        canvas_draw_str(c, 2, 36, buf);
        snprintf(buf, sizeof(buf), "RSSI %d dBm", s.last_rssi);
        canvas_draw_str(c, 2, 46, buf);
    } else {
        canvas_draw_str(c, 2, 36, "listening…");
    }
    snprintf(buf, sizeof(buf), "join rx:%lu tx:%lu", s.join_rx_count, s.join_tx_count);
    canvas_draw_str(c, 2, 56, buf);
    canvas_draw_str(c, 2, 63, "^=test-tx back=quit");
}

static void input_cb(InputEvent* ev, void* ctx) {
    App* app = ctx;
    furi_message_queue_put(app->input_queue, ev, FuriWaitForever);
}

// Direct-subscription callback on the RECORD_INPUT_EVENTS pubsub. Fires
// for BOTH hardware events (before the GUI filter) and CLI events (which
// the GUI filter would otherwise drop). We fan them into the same queue.
static void input_pubsub_cb(const void* message, void* ctx) {
    App* app = ctx;
    const InputEvent* ev = message;
    // Hardware events also arrive here — we let the GUI dispatch handle
    // those via input_cb. Filter to CLI (software) events only to avoid
    // duplicate queueing.
    if(ev->sequence_source == INPUT_SEQUENCE_SOURCE_HARDWARE) return;
    furi_message_queue_put(app->input_queue, ev, 0);
}

// CLI command: `sense_ap tx` fires a test TX; anything else prints usage.
// Runs on the CLI's own thread, so we just poke the pending flag and
// return — the RX worker consumes it. That path was blocked when we
// tried `input send up short` because Flipper's GUI service filters CLI
// input events that don't have a matching physical Press event; a custom
// CLI command sidesteps the whole GUI input state machine.
static void sense_ap_cli_cb(PipeSide* pipe, FuriString* args, void* context) {
    UNUSED(pipe);
    App* app = context;
    const char* arg = furi_string_get_cstr(args);
    if(strncmp(arg, "tx", 2) == 0) {
        app->test_tx_pending = true;
        printf("test-TX queued\r\n");
    } else {
        printf("usage: sense_ap tx\r\n");
    }
}

// Loader's "close current app" path is furi_thread_signal(app_thread,
// FuriSignalExit, NULL). Without a handler `loader_signal` returns false
// and the CLI prints "has to be closed manually" (loader_cli.c:85).
// Handle it by flipping `running` and injecting a synthetic Back event
// so the main loop wakes up immediately.
static bool exit_signal_cb(uint32_t signal, void* arg, void* context) {
    UNUSED(arg);
    App* app = context;
    if(signal == FuriSignalExit) {
        app->state->running = false;
        InputEvent wake = {.type = InputTypeShort, .key = InputKeyBack};
        furi_message_queue_put(app->input_queue, &wake, 0);
        return true;
    }
    return false;
}

// ── RX worker thread ────────────────────────────────────────────────

static int32_t rx_thread(void* ctx) {
    App* app = ctx;
    AppState* s = app->state;

    FURI_LOG_I(TAG, "starting RX worker");

    // Ownership
    furi_hal_subghz_reset();

    // Preset — writes registers then PATable
    furi_hal_subghz_load_custom_preset((uint8_t*)sense_cc1101_preset);

    // set_frequency_and_path sets both the CC1101 tuning registers AND the
    // external SPDT antenna switch (via CC1101 GDO2 + gpio_rf_sw_0). Plain
    // set_frequency skips the switch — RX still works because the switch was
    // left in a passable state after boot, but TX RF then goes into the
    // RX-tuned path and never reaches the antenna. Cost us hours of "chip
    // enters TX state cleanly but no signal on the SDR" debugging.
    furi_hal_subghz_set_frequency_and_path(SENSE_FREQ);

    // Verify the preset actually reached the CC1101.
    // Expected with our preset loaded: MDMCFG4=2D MDMCFG3=3B MDMCFG2=13
    //   DEVIATN=62 SYNC1=D3 SYNC0=91 PKTCTRL0=41 IOCFG0=06
    // CC1101 defaults are:            MDMCFG4=8C MDMCFG3=22 MDMCFG2=02
    //   DEVIATN=47 SYNC1=D3 SYNC0=91 PKTCTRL0=45 IOCFG0=2E (after furi reset)
    FURI_LOG_I(
        TAG,
        "regs after preset: IOCFG0=%02X SYNC1=%02X SYNC0=%02X PKTCTRL0=%02X MDMCFG4=%02X MDMCFG3=%02X MDMCFG2=%02X DEVIATN=%02X",
        cc1101_read_config_reg(0x02),
        cc1101_read_config_reg(0x04),
        cc1101_read_config_reg(0x05),
        cc1101_read_config_reg(0x08),
        cc1101_read_config_reg(0x10),
        cc1101_read_config_reg(0x11),
        cc1101_read_config_reg(0x12),
        cc1101_read_config_reg(0x15));

    // Enter RX (issues SRX strobe internally)
    furi_hal_subghz_rx();

    uint8_t frame[64];

    while(s->running) {
        // Manual test-TX: UP arrow on the Flipper sends a canned Join reply
        // to a fake Cookie address `CA FE F0 0D`, TID 0x42. Lets us iterate
        // on TX code without needing a live Join broadcast every time.
        if(app->test_tx_pending) {
            app->test_tx_pending = false;
            static const uint8_t FAKE_COOKIE[4] = {0xCA, 0xFE, 0xF0, 0x0D};
            uint8_t reply[24];
            size_t reply_len = build_join_reply(reply, FAKE_COOKIE, 0x42);
            FURI_LOG_I(TAG, "manual test-TX (fake cookie CAFEF00D)");
            if(cc1101_tx_packet(reply, reply_len)) {
                FURI_LOG_I(TAG, "test-TX ok");
                furi_mutex_acquire(s->mutex, FuriWaitForever);
                s->join_tx_count++;
                furi_mutex_release(s->mutex);
            } else {
                FURI_LOG_W(TAG, "test-TX failed");
            }
            cc1101_strobe(CC1101_STROBE_SFRX);
            furi_hal_subghz_rx();
        }

        // Poll RXBYTES. Datasheet: read this register twice; if the
        // second read matches the first, the value is stable. Bit 7
        // is RXFIFO_OVERFLOW.
        uint8_t rxb1 = cc1101_read_status_reg(CC1101_STATUS_RXBYTES);
        uint8_t rxb2 = cc1101_read_status_reg(CC1101_STATUS_RXBYTES);
        if(rxb1 != rxb2) {
            furi_delay_ms(1);
            continue;
        }
        bool overflow = rxb1 & 0x80;
        uint8_t nbytes = rxb1 & 0x7F;

        if(overflow) {
            FURI_LOG_W(TAG, "RXFIFO overflow, flushing");
            cc1101_strobe(CC1101_STROBE_SIDLE);
            cc1101_strobe(CC1101_STROBE_SFRX);
            cc1101_strobe(CC1101_STROBE_SRX);
            furi_delay_ms(2);
            continue;
        }

        // Wait until we have a plausible whole frame. With PKTCTRL0
        // WHITE=1, LENGTH_CONFIG=01, and APPEND_STATUS=1 the CC1101
        // will present: [LEN][data * LEN][RSSI][LQI/CRC]. Minimum
        // sen.se frame length observed: 11 bytes (port-7 PLL beacon)
        // → total 11 + 1 + 2 = 14.
        if(nbytes < 3) {
            furi_delay_ms(2);
            continue;
        }

        // Peek the length byte
        uint8_t len_byte = 0;
        cc1101_read_fifo(&len_byte, 1);
        size_t remaining = (size_t)len_byte + 2; // payload + 2 status bytes
        if(remaining > sizeof(frame) - 1) {
            FURI_LOG_W(TAG, "impossible length %u — flushing", len_byte);
            cc1101_strobe(CC1101_STROBE_SIDLE);
            cc1101_strobe(CC1101_STROBE_SFRX);
            cc1101_strobe(CC1101_STROBE_SRX);
            s->bad_count++;
            continue;
        }

        // Wait for the rest of the packet to land in the FIFO.
        for(int spin = 0; spin < 200; spin++) {
            uint8_t nb1 = cc1101_read_status_reg(CC1101_STATUS_RXBYTES) & 0x7F;
            uint8_t nb2 = cc1101_read_status_reg(CC1101_STATUS_RXBYTES) & 0x7F;
            if(nb1 == nb2 && nb1 >= remaining) break;
            furi_delay_ms(1);
        }

        frame[0] = len_byte;
        cc1101_read_fifo(&frame[1], remaining);
        // status bytes: frame[1 + len_byte] = RSSI, [+1] = LQI (bit7 = CRC_OK, ignored w/ HW CRC off)
        uint8_t rssi_raw = frame[1 + len_byte];
        int rssi = cc1101_decode_rssi(rssi_raw);
        size_t frame_len = 1 + len_byte; // just the on-air bytes for parsing

        // NOTE: with PKTCTRL0.WHITE_DATA=1 the CC1101 already applied
        // PN9 dewhitening on the way out of the FIFO. The pn9_dewhiten()
        // helper is kept in the source for raw-mode captures (WHITE=0).

        SenseFrame f;
        if(!sense_frame_parse(frame, frame_len, &f)) {
            s->bad_count++;
            FURI_LOG_W(TAG, "malformed frame len=%u", len_byte);
            continue;
        }

        // Hex-dump the payload for the log
        char payload_hex[64] = {0};
        size_t off = 0;
        for(size_t i = 0; i < f.payload_len && off < sizeof(payload_hex) - 3; i++) {
            off += snprintf(payload_hex + off, sizeof(payload_hex) - off, "%02x", f.payload[i]);
        }

        FURI_LOG_I(
            TAG,
            "len=%u dst=%02x%02x%02x%02x src=%02x%02x%02x%02x port=%u(%s) fwd=%u sender=%u rssi=%d payload=%s%s",
            f.length,
            f.dstaddr[0],
            f.dstaddr[1],
            f.dstaddr[2],
            f.dstaddr[3],
            f.srcaddr[0],
            f.srcaddr[1],
            f.srcaddr[2],
            f.srcaddr[3],
            f.port,
            f.encrypted ? "ENC" : "PT",
            f.fwd,
            f.sender,
            rssi,
            payload_hex,
            sense_frame_is_join(&f) ? " <JOIN>" : "");

        bool is_join = sense_frame_is_join(&f);

        furi_mutex_acquire(s->mutex, FuriWaitForever);
        s->frame_count++;
        memcpy(s->last_src, f.srcaddr, 4);
        s->last_port = f.port;
        s->last_rssi = rssi;
        s->last_join = is_join;
        if(is_join) s->join_rx_count++;
        furi_mutex_release(s->mutex);

        // Phase 2: reply to Join broadcasts.
        // Sen.se's variant has a 1-byte prefix before the standard SimpliciTI
        // Join body, so TID lives at payload[2] not payload[1]. See JOIN.md.
        if(is_join && f.payload_len >= 3) {
            uint8_t tid = f.payload[2];
            uint8_t reply[24];
            size_t reply_len = build_join_reply(reply, f.srcaddr, tid);

            FURI_LOG_I(
                TAG,
                "sending Join reply to %02x%02x%02x%02x tid=%u",
                f.srcaddr[0],
                f.srcaddr[1],
                f.srcaddr[2],
                f.srcaddr[3],
                tid);

            if(cc1101_tx_packet(reply, reply_len)) {
                furi_mutex_acquire(s->mutex, FuriWaitForever);
                s->join_tx_count++;
                furi_mutex_release(s->mutex);
                FURI_LOG_I(TAG, "Join reply sent");
            } else {
                FURI_LOG_W(TAG, "Join reply TX failed");
            }

            // Back to RX. MCSM1 default takes us to IDLE after TX; kick RX
            // explicitly (and flush any stale bytes that arrived during TX).
            cc1101_strobe(CC1101_STROBE_SFRX);
            furi_hal_subghz_rx();
        }
    }

    // Cleanup: return radio to IDLE
    cc1101_strobe(CC1101_STROBE_SIDLE);
    furi_hal_subghz_sleep();
    FURI_LOG_I(TAG, "RX worker exiting");
    return 0;
}

// ── Entry point ─────────────────────────────────────────────────────

int32_t sense_mother_ap_main(void* p) {
    UNUSED(p);

    App app = {0};
    AppState state = {0};
    state.mutex = furi_mutex_alloc(FuriMutexTypeNormal);
    state.running = true;
    app.state = &state;
    app.input_queue = furi_message_queue_alloc(8, sizeof(InputEvent));

    ViewPort* vp = view_port_alloc();
    view_port_draw_callback_set(vp, render_cb, &app);
    view_port_input_callback_set(vp, input_cb, &app);

    Gui* gui = furi_record_open(RECORD_GUI);
    gui_add_view_port(gui, vp, GuiLayerFullscreen);

    // Ask nicely for exclusive radio access
    furi_hal_power_suppress_charge_enter();

    // Handle Loader's graceful-exit signal so we can be replaced without
    // the user having to back out manually.
    furi_thread_set_signal_callback(furi_thread_get_current(), exit_signal_cb, &app);

    // Subscribe directly to the input events pubsub so we can pick up
    // CLI-injected events that the GUI dispatcher would otherwise filter.
    app.input_events = furi_record_open(RECORD_INPUT_EVENTS);
    app.input_sub = furi_pubsub_subscribe(app.input_events, input_pubsub_cb, &app);

    // Register `sense_ap tx` CLI command so a script can trigger a test-TX
    // over USB CDC without a physical button press.
    CliRegistry* cli = furi_record_open(RECORD_CLI);
    cli_registry_add_command(cli, "sense_ap", CliCommandFlagParallelSafe, sense_ap_cli_cb, &app);
    furi_record_close(RECORD_CLI);

    app.rx_thread = furi_thread_alloc_ex("SenseRX", 4096, rx_thread, &app);
    furi_thread_start(app.rx_thread);

    InputEvent ev;
    while(true) {
        if(furi_message_queue_get(app.input_queue, &ev, 100) == FuriStatusOk) {
            FURI_LOG_I(TAG, "input key=%u type=%u seq=%lu", ev.key, ev.type, ev.sequence);
            if(ev.type == InputTypeShort && ev.key == InputKeyBack) break;
            // Fire test-TX on UP regardless of type (Press / Short / Release).
            // CLI `input send up short` synthesizes a single InputTypeShort;
            // physical UP goes Press → Release → Short after debounce. Any of
            // them counts as "user asked for a test-TX", we just dedupe by
            // clearing the pending flag when the worker consumes it.
            if(ev.key == InputKeyUp) {
                app.test_tx_pending = true;
            }
        }
        view_port_update(vp);
    }

    state.running = false;
    furi_thread_join(app.rx_thread);
    furi_thread_free(app.rx_thread);

    furi_thread_set_signal_callback(furi_thread_get_current(), NULL, NULL);

    furi_pubsub_unsubscribe(app.input_events, app.input_sub);
    furi_record_close(RECORD_INPUT_EVENTS);

    {
        CliRegistry* cli = furi_record_open(RECORD_CLI);
        cli_registry_delete_command(cli, "sense_ap");
        furi_record_close(RECORD_CLI);
    }

    furi_hal_power_suppress_charge_exit();

    view_port_enabled_set(vp, false);
    gui_remove_view_port(gui, vp);
    view_port_free(vp);
    furi_record_close(RECORD_GUI);
    furi_message_queue_free(app.input_queue);
    furi_mutex_free(state.mutex);

    return 0;
}

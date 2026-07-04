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
#include <string.h>

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
#define CC1101_STROBE_SIDLE 0x36
#define CC1101_STROBE_SFRX  0x3A
#define CC1101_STROBE_SNOP  0x3D

#define CC1101_STATUS_RXBYTES   0x3B
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

// CC1101 RSSI decode (datasheet §17.3): signed offset + fixed -74 offset.
static int cc1101_decode_rssi(uint8_t raw) {
    int r = raw >= 128 ? (int)raw - 256 : (int)raw;
    return (r / 2) - 74;
}

// ── UI state ────────────────────────────────────────────────────────

typedef struct {
    FuriMutex* mutex;
    uint32_t frame_count;
    uint32_t bad_count;
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
        canvas_draw_str(c, 2, 48, buf);
    } else {
        canvas_draw_str(c, 2, 36, "listening…");
    }
    canvas_draw_str(c, 2, 62, "back = quit");
}

static void input_cb(InputEvent* ev, void* ctx) {
    App* app = ctx;
    furi_message_queue_put(app->input_queue, ev, FuriWaitForever);
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

    // Frequency + path. Newer OFW/Momentum both accept plain set_frequency
    // and internally pick the path filter.
    furi_hal_subghz_set_frequency(SENSE_FREQ);

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

        furi_mutex_acquire(s->mutex, FuriWaitForever);
        s->frame_count++;
        memcpy(s->last_src, f.srcaddr, 4);
        s->last_port = f.port;
        s->last_rssi = rssi;
        s->last_join = sense_frame_is_join(&f);
        furi_mutex_release(s->mutex);
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

    app.rx_thread = furi_thread_alloc_ex("SenseRX", 4096, rx_thread, &app);
    furi_thread_start(app.rx_thread);

    InputEvent ev;
    while(true) {
        if(furi_message_queue_get(app.input_queue, &ev, 100) == FuriStatusOk) {
            if(ev.type == InputTypeShort && ev.key == InputKeyBack) break;
        }
        view_port_update(vp);
    }

    state.running = false;
    furi_thread_join(app.rx_thread);
    furi_thread_free(app.rx_thread);

    furi_thread_set_signal_callback(furi_thread_get_current(), NULL, NULL);

    furi_hal_power_suppress_charge_exit();

    view_port_enabled_set(vp, false);
    gui_remove_view_port(gui, vp);
    view_port_free(vp);
    furi_record_close(RECORD_GUI);
    furi_message_queue_free(app.input_queue);
    furi_mutex_free(state.mutex);

    return 0;
}

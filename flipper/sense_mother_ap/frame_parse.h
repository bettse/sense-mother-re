#pragma once

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

/**
 * SimpliciTI frame layout (after CC1101 sync + PN9 dewhitening):
 *
 *   LENGTH | DSTADDR(4) | SRCADDR(4) | PORT | DEVINFO | payload | FCS(2)
 *
 * See simpliciti/simpliciti-1.2.0-mspgcc/Documents/SimpliciTI Specification.pdf
 * §5, Figures 7-8, Tables 1-3.
 */
typedef struct {
    uint8_t length;
    uint8_t dstaddr[4];
    uint8_t srcaddr[4];
    uint8_t port_byte;
    uint8_t devinfo_byte;
    // Decoded PORT bit-field (SimpliciTI Spec Table 2)
    bool fwd;
    bool encrypted;
    uint8_t port; // 0-63
    // Decoded DEVINFO bit-field (SimpliciTI Spec Table 3)
    bool ack_req;
    bool sleep;
    uint8_t sender; // 0=ED, 1=RangeExt, 2=AP, 3=reserved
    bool ack_rep;
    uint8_t hopcount; // 0-7
    // Payload slice (points into caller's buffer)
    const uint8_t* payload;
    size_t payload_len;
} SenseFrame;

/**
 * Parse a dewhitened SimpliciTI frame. `data` starts at the LENGTH byte
 * (i.e. sync word already stripped, PN9 already applied).
 *
 * Returns true if the frame is structurally valid (length coherent
 * with buffer). Does not verify FCS.
 */
bool sense_frame_parse(const uint8_t* data, size_t len, SenseFrame* out);

/**
 * True if this frame's port-3 payload carries the sen.se Join Token
 * `08 07 06 05` at the expected offset (payload[3..7]). This is the
 * signal that a Cookie is asking to be linked.
 */
bool sense_frame_is_join(const SenseFrame* f);

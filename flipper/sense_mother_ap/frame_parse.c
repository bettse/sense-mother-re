#include "frame_parse.h"
#include <string.h>

bool sense_frame_parse(const uint8_t* data, size_t len, SenseFrame* out) {
    if(len < 11) return false;

    out->length = data[0];

    // The LENGTH field counts bytes AFTER itself; total frame = length + 1.
    if((size_t)out->length + 1 > len) return false;
    if(out->length < 10) return false;

    memcpy(out->dstaddr, &data[1], 4);
    memcpy(out->srcaddr, &data[5], 4);
    out->port_byte = data[9];
    out->devinfo_byte = data[10];

    // SimpliciTI Spec Table 2
    out->fwd = (out->port_byte >> 7) & 1;
    out->encrypted = (out->port_byte >> 6) & 1;
    out->port = out->port_byte & 0x3F;

    // SimpliciTI Spec Table 3
    out->ack_req = (out->devinfo_byte >> 7) & 1;
    out->sleep = (out->devinfo_byte >> 6) & 1;
    out->sender = (out->devinfo_byte >> 4) & 0x3;
    out->ack_rep = (out->devinfo_byte >> 3) & 1;
    out->hopcount = out->devinfo_byte & 0x7;

    // Payload = everything after LEN+DST+SRC+PORT+DEVINFO (11 bytes) up
    // to the LEN-declared frame end. With CC1101 CRC_EN=0 the on-air FCS
    // bytes are past the LEN count and not in this buffer, so we don't
    // strip anything.
    size_t total = (size_t)out->length + 1;
    out->payload = &data[11];
    out->payload_len = total > 11 ? total - 11 : 0;

    return true;
}

bool sense_frame_is_join(const SenseFrame* f) {
    // Port-3 broadcast with `08 07 06 05` at payload offset 3
    // See README "Cookie Join broadcast (port 3)"
    if(f->port != 3) return false;
    if(f->payload_len < 7) return false;
    return f->payload[3] == 0x08 && f->payload[4] == 0x07 &&
           f->payload[5] == 0x06 && f->payload[6] == 0x05;
}

/*
 * kbfiltr.h — shared definitions between kbfiltr.sys and the synapless service.
 *
 * Include this header in both the driver (kernel mode) and the Python ctypes
 * wrapper (usermode).  Only plain C types — no WDM includes required here.
 */

#pragma once

/* ── IOCTL ─────────────────────────────────────────────────────────────────── */

/*
 * Set the list of PS/2 scan codes that the filter should suppress.
 *
 *   Input buffer : array of USHORT scan codes  (up to SYNAPLESS_MAX_MACRO_KEYS)
 *   Output buffer: none
 *
 * Passing an empty array (cbInput == 0) clears the list.
 */
#define SYNAPLESS_DEVICE_TYPE  0x8031          /* custom, above 0x8000 */
#define SYNAPLESS_IOCTL_BASE   0x800

#ifndef CTL_CODE
#  define CTL_CODE(DeviceType, Function, Method, Access) \
     (((DeviceType) << 16) | ((Access) << 14) | ((Function) << 2) | (Method))
#  define METHOD_BUFFERED   0
#  define FILE_WRITE_ACCESS 0x0002
#endif

#define IOCTL_SYNAPLESS_SET_MACRO_KEYS \
    CTL_CODE(SYNAPLESS_DEVICE_TYPE, SYNAPLESS_IOCTL_BASE + 1, \
             METHOD_BUFFERED, FILE_WRITE_ACCESS)

/* ── Limits ────────────────────────────────────────────────────────────────── */

#define SYNAPLESS_MAX_MACRO_KEYS 64

/* ── Key event (output of ReadFile on \\.\SynaplessFilter) ─────────────────── */

/*
 * One struct is returned per suppressed physical key transition.
 * Flags mirrors KEYBOARD_INPUT_DATA.Flags (KEY_MAKE=0, KEY_BREAK=1, E0=2, E1=4).
 */
#pragma pack(push, 1)
typedef struct _SYNAPLESS_KEY_EVENT {
    unsigned short MakeCode;
    unsigned short Flags;
} SYNAPLESS_KEY_EVENT, *PSYNAPLESS_KEY_EVENT;
#pragma pack(pop)

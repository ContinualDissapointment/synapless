/*
 * kbfiltr.c — Synapless WDM keyboard filter driver
 *
 * Attaches as an upper filter on Razer Tartarus Pro keyboard HID interfaces
 * (matched via the INF hardware IDs HID\VID_1532&PID_0244).
 *
 * Architecture
 * ────────────
 * The driver creates one control device (\Device\SynaplessFilter /
 * \DosDevices\SynaplessFilter) that the synapless service opens from usermode.
 *
 * Each time Windows enumerates a matching HID device, AddDevice() creates a
 * filter device object and attaches it above kbdhid.sys.  The filter
 * intercepts IOCTL_INTERNAL_KEYBOARD_CONNECT, saves the class service pointer,
 * and substitutes KbfiltrServiceCallback().
 *
 * KbfiltrServiceCallback() runs at DISPATCH_LEVEL.  For every incoming
 * KEYBOARD_INPUT_DATA record it checks whether the scan code is in the
 * macro-key list stored in the control device extension.  Macro keys are
 * swallowed and the record is put into a cancel-safe IRP queue so that the
 * next pending ReadFile() from usermode can drain it.  Non-macro keys are
 * forwarded directly to the class service.
 *
 * Deduplication: the Tartarus Pro exposes two keyboard HID interfaces; both
 * fire the service callback for the same physical key.  A 15 ms per-scan-code
 * timestamp suppresses the duplicate.
 *
 * Usermode protocol (see service/kbfiltr_client.py):
 *   1. CreateFile("\\\\.\\SynaplessFilter", ...)
 *   2. DeviceIoControl(IOCTL_SYNAPLESS_SET_MACRO_KEYS, scanCodes, n*2)
 *   3. Loop: ReadFile() — blocks until a suppressed key event is available.
 *            Returns one SYNAPLESS_KEY_EVENT per call.
 */

#include <wdm.h>
#include <kbdmou.h>
#include <ntddkbd.h>
#include "kbfiltr.h"

/* ── Constants ──────────────────────────────────────────────────────────────── */

#define DRIVER_TAG    'lFbK'   /* pool tag: 'KbFl' reversed */
#define DEDUP_100NS   150000ULL /* 15 ms in 100-ns units     */

static const UNICODE_STRING gDeviceName =
    RTL_CONSTANT_STRING(L"\\Device\\SynaplessFilter");
static const UNICODE_STRING gSymlinkName =
    RTL_CONSTANT_STRING(L"\\DosDevices\\SynaplessFilter");

/* ── Device extensions ──────────────────────────────────────────────────────── */

/* Control device (singleton) — holds macro list and IRP queue */
typedef struct _CTRL_EXT {
    IO_CSQ     Csq;
    KSPIN_LOCK CsqLock;
    LIST_ENTRY CsqList;

    KSPIN_LOCK MacroLock;
    USHORT     MacroCodes[SYNAPLESS_MAX_MACRO_KEYS];
    ULONG      MacroCount;

    /* per-scan-code dedup timestamp (100-ns interrupt time) */
    ULONGLONG  LastFire[256];
} CTRL_EXT, *PCTRL_EXT;

/* Filter device (one per matched HID keyboard interface) */
typedef struct _FILT_EXT {
    PDEVICE_OBJECT Self;
    PDEVICE_OBJECT Lower;
    CONNECT_DATA   ConnectData; /* saved class service data */
    BOOLEAN        Connected;
} FILT_EXT, *PFILT_EXT;

/* ── Globals ─────────────────────────────────────────────────────────────────── */

static PDEVICE_OBJECT gCtrlDevice = NULL;

/* ── Forward declarations ───────────────────────────────────────────────────── */

DRIVER_INITIALIZE DriverEntry;
DRIVER_UNLOAD     KbfiltrUnload;
DRIVER_ADD_DEVICE KbfiltrAddDevice;
DRIVER_DISPATCH   KbfiltrPassThrough;
DRIVER_DISPATCH   KbfiltrInternalDeviceControl;
DRIVER_DISPATCH   KbfiltrPnP;
DRIVER_DISPATCH   KbfiltrPower;
DRIVER_DISPATCH   KbfiltrCreateClose;
DRIVER_DISPATCH   KbfiltrRead;
DRIVER_DISPATCH   KbfiltrDeviceControl;

/* Cancel-safe queue callbacks */
static VOID   CsqInsertIrp(PIO_CSQ Csq, PIRP Irp);
static VOID   CsqRemoveIrp(PIO_CSQ Csq, PIRP Irp);
static PIRP   CsqPeekNextIrp(PIO_CSQ Csq, PIRP Irp, PVOID PeekContext);
static VOID   CsqAcquireLock(PIO_CSQ Csq, PKIRQL Irql);
static VOID   CsqReleaseLock(PIO_CSQ Csq, KIRQL Irql);
static VOID   CsqCompleteCancelledIrp(PIO_CSQ Csq, PIRP Irp);

/* Keyboard class service callback (substituted into CONNECT_DATA) */
static VOID KbfiltrServiceCallback(
    IN PDEVICE_OBJECT DeviceObject,
    IN PKEYBOARD_INPUT_DATA InputDataStart,
    IN PKEYBOARD_INPUT_DATA InputDataEnd,
    IN OUT PULONG InputDataConsumed);

/* ── Helper: pass IRP straight to lower driver ──────────────────────────────── */

NTSTATUS KbfiltrPassThrough(PDEVICE_OBJECT DeviceObject, PIRP Irp)
{
    PFILT_EXT ext = (PFILT_EXT)DeviceObject->DeviceExtension;
    IoSkipCurrentIrpStackLocation(Irp);
    return IoCallDriver(ext->Lower, Irp);
}

/* ── Cancel-safe queue ──────────────────────────────────────────────────────── */

static VOID CsqInsertIrp(PIO_CSQ Csq, PIRP Irp)
{
    PCTRL_EXT ext = CONTAINING_RECORD(Csq, CTRL_EXT, Csq);
    InsertTailList(&ext->CsqList, &Irp->Tail.Overlay.ListEntry);
}

static VOID CsqRemoveIrp(PIO_CSQ Csq, PIRP Irp)
{
    UNREFERENCED_PARAMETER(Csq);
    RemoveEntryList(&Irp->Tail.Overlay.ListEntry);
}

static PIRP CsqPeekNextIrp(PIO_CSQ Csq, PIRP Irp, PVOID PeekContext)
{
    PCTRL_EXT  ext   = CONTAINING_RECORD(Csq, CTRL_EXT, Csq);
    PLIST_ENTRY head  = &ext->CsqList;
    PLIST_ENTRY next;
    UNREFERENCED_PARAMETER(PeekContext);

    next = (Irp == NULL) ? head->Flink
                         : Irp->Tail.Overlay.ListEntry.Flink;

    while (next != head) {
        PIRP irp = CONTAINING_RECORD(next, IRP, Tail.Overlay.ListEntry);
        return irp;
    }
    return NULL;
}

static VOID CsqAcquireLock(PIO_CSQ Csq, PKIRQL Irql)
{
    PCTRL_EXT ext = CONTAINING_RECORD(Csq, CTRL_EXT, Csq);
    KeAcquireSpinLock(&ext->CsqLock, Irql);
}

static VOID CsqReleaseLock(PIO_CSQ Csq, KIRQL Irql)
{
    PCTRL_EXT ext = CONTAINING_RECORD(Csq, CTRL_EXT, Csq);
    KeReleaseSpinLock(&ext->CsqLock, Irql);
}

static VOID CsqCompleteCancelledIrp(PIO_CSQ Csq, PIRP Irp)
{
    UNREFERENCED_PARAMETER(Csq);
    Irp->IoStatus.Status      = STATUS_CANCELLED;
    Irp->IoStatus.Information = 0;
    IoCompleteRequest(Irp, IO_NO_INCREMENT);
}

/* ── Keyboard service callback ──────────────────────────────────────────────── */

/*
 * Called by kbdhid.sys at DISPATCH_LEVEL for every physical key event on the
 * Tartarus interface this filter is attached to.
 *
 * DeviceObject is set to our filter device (we replaced ClassDeviceObject in
 * the connect data with our own device pointer so we can reach FILT_EXT).
 */
static VOID KbfiltrServiceCallback(
    IN PDEVICE_OBJECT       DeviceObject,
    IN PKEYBOARD_INPUT_DATA InputDataStart,
    IN PKEYBOARD_INPUT_DATA InputDataEnd,
    IN OUT PULONG           InputDataConsumed)
{
    PFILT_EXT            filtExt = (PFILT_EXT)DeviceObject->DeviceExtension;
    PCTRL_EXT            ctrlExt;
    PKEYBOARD_INPUT_DATA cur;
    ULONG                consumed = 0;

    if (!gCtrlDevice) goto forward_all;
    ctrlExt = (PCTRL_EXT)gCtrlDevice->DeviceExtension;

    for (cur = InputDataStart; cur < InputDataEnd; cur++) {
        USHORT    code   = cur->MakeCode;
        BOOLEAN   isMacro = FALSE;
        ULONG     i;
        ULONGLONG now;

        /* Check macro list (under spin lock — we're at DISPATCH_LEVEL already) */
        KeAcquireSpinLockAtDpcLevel(&ctrlExt->MacroLock);
        for (i = 0; i < ctrlExt->MacroCount; i++) {
            if (ctrlExt->MacroCodes[i] == code) { isMacro = TRUE; break; }
        }
        KeReleaseSpinLockFromDpcLevel(&ctrlExt->MacroLock);

        if (!isMacro) {
            /* Forward this record to the class service (non-macro key). */
            ULONG single = 1;
#pragma warning(suppress: 4152)
            ((PSERVICE_CALLBACK_ROUTINE)filtExt->ConnectData.ClassService)(
                filtExt->ConnectData.ClassDeviceObject,
                cur, cur + 1, &single);
            consumed++;
            continue;
        }

        /* Dedup: the Tartarus has two keyboard HID interfaces; suppress the
           second WM_INPUT that arrives within 15 ms for the same scan code. */
        now = KeQueryInterruptTime();
        if (code < 256) {
            if (now - ctrlExt->LastFire[code] < DEDUP_100NS) {
                consumed++;
                continue; /* duplicate — swallow silently */
            }
            ctrlExt->LastFire[code] = now;
        }

        /* Notify usermode: complete the oldest pending ReadFile IRP. */
        {
            PIRP pending = IoCsqRemoveNextIrp(&ctrlExt->Csq, NULL);
            if (pending) {
                PSYNAPLESS_KEY_EVENT evt =
                    (PSYNAPLESS_KEY_EVENT)pending->AssociatedIrp.SystemBuffer;
                evt->MakeCode = cur->MakeCode;
                evt->Flags    = cur->Flags;
                pending->IoStatus.Status      = STATUS_SUCCESS;
                pending->IoStatus.Information = sizeof(SYNAPLESS_KEY_EVENT);
                IoCompleteRequest(pending, IO_NO_INCREMENT);
            }
            /* If no pending IRP the event is dropped — Python polls fast enough. */
        }
        consumed++;
    }

    *InputDataConsumed = consumed;
    return;

forward_all:
    /* Control device not ready — pass everything through unmodified. */
#pragma warning(suppress: 4152)
    ((PSERVICE_CALLBACK_ROUTINE)filtExt->ConnectData.ClassService)(
        filtExt->ConnectData.ClassDeviceObject,
        InputDataStart, InputDataEnd, InputDataConsumed);
}

/* ── IRP_MJ_INTERNAL_DEVICE_CONTROL ────────────────────────────────────────── */

NTSTATUS KbfiltrInternalDeviceControl(PDEVICE_OBJECT DeviceObject, PIRP Irp)
{
    PFILT_EXT           filtExt = (PFILT_EXT)DeviceObject->DeviceExtension;
    PIO_STACK_LOCATION  stack   = IoGetCurrentIrpStackLocation(Irp);

    if (stack->Parameters.DeviceIoControl.IoControlCode
            == IOCTL_INTERNAL_KEYBOARD_CONNECT) {

        if (filtExt->Connected) {
            /* Already connected — reject duplicate. */
            Irp->IoStatus.Status = STATUS_SHARING_VIOLATION;
            IoCompleteRequest(Irp, IO_NO_INCREMENT);
            return STATUS_SHARING_VIOLATION;
        }

        /* Save what kbdclass sent us, then replace with our own pointers. */
        filtExt->ConnectData =
            *(PCONNECT_DATA)stack->Parameters.DeviceIoControl.Type3InputBuffer;

        ((PCONNECT_DATA)stack->Parameters.DeviceIoControl.Type3InputBuffer)
            ->ClassDeviceObject = filtExt->Self;
#pragma warning(push)
#pragma warning(disable: 4152)
        ((PCONNECT_DATA)stack->Parameters.DeviceIoControl.Type3InputBuffer)
            ->ClassService = KbfiltrServiceCallback;
#pragma warning(pop)

        filtExt->Connected = TRUE;
    }

    /* Forward to lower driver. */
    IoSkipCurrentIrpStackLocation(Irp);
    return IoCallDriver(filtExt->Lower, Irp);
}

/* ── IRP_MJ_PNP ─────────────────────────────────────────────────────────────── */

NTSTATUS KbfiltrPnP(PDEVICE_OBJECT DeviceObject, PIRP Irp)
{
    PFILT_EXT          filtExt = (PFILT_EXT)DeviceObject->DeviceExtension;
    PIO_STACK_LOCATION stack   = IoGetCurrentIrpStackLocation(Irp);

    if (stack->MinorFunction == IRP_MN_REMOVE_DEVICE) {
        IoSkipCurrentIrpStackLocation(Irp);
        IoCallDriver(filtExt->Lower, Irp);
        IoDetachDevice(filtExt->Lower);
        IoDeleteDevice(DeviceObject);
        return STATUS_SUCCESS;
    }

    /* All other PnP — pass through. */
    IoSkipCurrentIrpStackLocation(Irp);
    return IoCallDriver(filtExt->Lower, Irp);
}

/* ── IRP_MJ_POWER ───────────────────────────────────────────────────────────── */

NTSTATUS KbfiltrPower(PDEVICE_OBJECT DeviceObject, PIRP Irp)
{
    PFILT_EXT filtExt = (PFILT_EXT)DeviceObject->DeviceExtension;
    PoStartNextPowerIrp(Irp);
    IoSkipCurrentIrpStackLocation(Irp);
    return PoCallDriver(filtExt->Lower, Irp);
}

/* ── Control device dispatch ────────────────────────────────────────────────── */

NTSTATUS KbfiltrCreateClose(PDEVICE_OBJECT DeviceObject, PIRP Irp)
{
    UNREFERENCED_PARAMETER(DeviceObject);
    Irp->IoStatus.Status      = STATUS_SUCCESS;
    Irp->IoStatus.Information = 0;
    IoCompleteRequest(Irp, IO_NO_INCREMENT);
    return STATUS_SUCCESS;
}

/* ReadFile — block until a suppressed key event is available. */
NTSTATUS KbfiltrRead(PDEVICE_OBJECT DeviceObject, PIRP Irp)
{
    PCTRL_EXT          ctrlExt = (PCTRL_EXT)DeviceObject->DeviceExtension;
    PIO_STACK_LOCATION stack   = IoGetCurrentIrpStackLocation(Irp);

    if (stack->Parameters.Read.Length < sizeof(SYNAPLESS_KEY_EVENT)) {
        Irp->IoStatus.Status      = STATUS_BUFFER_TOO_SMALL;
        Irp->IoStatus.Information = 0;
        IoCompleteRequest(Irp, IO_NO_INCREMENT);
        return STATUS_BUFFER_TOO_SMALL;
    }

    /* Queue the IRP; it will be completed by KbfiltrServiceCallback. */
    IoMarkIrpPending(Irp);
    IoCsqInsertIrp(&ctrlExt->Csq, Irp, NULL);
    return STATUS_PENDING;
}

/* DeviceIoControl — handle IOCTL_SYNAPLESS_SET_MACRO_KEYS. */
NTSTATUS KbfiltrDeviceControl(PDEVICE_OBJECT DeviceObject, PIRP Irp)
{
    PCTRL_EXT          ctrlExt = (PCTRL_EXT)DeviceObject->DeviceExtension;
    PIO_STACK_LOCATION stack   = IoGetCurrentIrpStackLocation(Irp);
    NTSTATUS           status  = STATUS_SUCCESS;
    ULONG_PTR          info    = 0;

    if (stack->Parameters.DeviceIoControl.IoControlCode
            != IOCTL_SYNAPLESS_SET_MACRO_KEYS) {
        status = STATUS_INVALID_DEVICE_REQUEST;
        goto done;
    }

    {
        ULONG   inLen = stack->Parameters.DeviceIoControl.InputBufferLength;
        PUSHORT codes = (PUSHORT)Irp->AssociatedIrp.SystemBuffer;
        ULONG   count = inLen / sizeof(USHORT);
        KIRQL   irql;

        if (count > SYNAPLESS_MAX_MACRO_KEYS) count = SYNAPLESS_MAX_MACRO_KEYS;

        KeAcquireSpinLock(&ctrlExt->MacroLock, &irql);
        RtlCopyMemory(ctrlExt->MacroCodes, codes, count * sizeof(USHORT));
        ctrlExt->MacroCount = count;
        KeReleaseSpinLock(&ctrlExt->MacroLock, irql);
    }

done:
    Irp->IoStatus.Status      = status;
    Irp->IoStatus.Information = info;
    IoCompleteRequest(Irp, IO_NO_INCREMENT);
    return status;
}

/* ── AddDevice ──────────────────────────────────────────────────────────────── */

NTSTATUS KbfiltrAddDevice(PDRIVER_OBJECT DriverObject, PDEVICE_OBJECT PhysicalDeviceObject)
{
    NTSTATUS       status;
    PDEVICE_OBJECT filterDevice = NULL;
    PFILT_EXT      filtExt;

    status = IoCreateDevice(
        DriverObject,
        sizeof(FILT_EXT),
        NULL,               /* no name — filter devices are unnamed */
        FILE_DEVICE_UNKNOWN,
        FILE_DEVICE_SECURE_OPEN,
        FALSE,
        &filterDevice);

    if (!NT_SUCCESS(status)) return status;

    filtExt             = (PFILT_EXT)filterDevice->DeviceExtension;
    filtExt->Self       = filterDevice;
    filtExt->Connected  = FALSE;
    RtlZeroMemory(&filtExt->ConnectData, sizeof(filtExt->ConnectData));

    filtExt->Lower = IoAttachDeviceToDeviceStack(filterDevice, PhysicalDeviceObject);
    if (!filtExt->Lower) {
        IoDeleteDevice(filterDevice);
        return STATUS_NO_SUCH_DEVICE;
    }

    /* Mirror flags from the lower device so buffering/alignment is consistent. */
    filterDevice->Flags |= filtExt->Lower->Flags & (DO_BUFFERED_IO | DO_DIRECT_IO);
    filterDevice->Flags &= ~DO_DEVICE_INITIALIZING;

    return STATUS_SUCCESS;
}

/* ── DriverEntry ────────────────────────────────────────────────────────────── */

NTSTATUS DriverEntry(PDRIVER_OBJECT DriverObject, PUNICODE_STRING RegistryPath)
{
    NTSTATUS  status;
    PCTRL_EXT ctrlExt;
    int       i;

    UNREFERENCED_PARAMETER(RegistryPath);

    /* Set up dispatch table.  All IRPs targeting filter devices go through
       KbfiltrPassThrough by default; specialised handlers override below. */
    for (i = 0; i <= IRP_MJ_MAXIMUM_FUNCTION; i++)
        DriverObject->MajorFunction[i] = KbfiltrPassThrough;

    /* Filter device dispatch — keyboard-specific overrides */
    DriverObject->MajorFunction[IRP_MJ_INTERNAL_DEVICE_CONTROL] =
        KbfiltrInternalDeviceControl;
    DriverObject->MajorFunction[IRP_MJ_PNP]   = KbfiltrPnP;
    DriverObject->MajorFunction[IRP_MJ_POWER]  = KbfiltrPower;

    /* Control device dispatch — usermode-facing overrides.
       We route by DeviceObject pointer in each handler, so they are safe to
       register globally: KbfiltrCreateClose / Read / DeviceControl check
       whether DeviceObject == gCtrlDevice and fall through otherwise. */
    DriverObject->MajorFunction[IRP_MJ_CREATE]         = KbfiltrCreateClose;
    DriverObject->MajorFunction[IRP_MJ_CLOSE]          = KbfiltrCreateClose;
    DriverObject->MajorFunction[IRP_MJ_READ]           = KbfiltrRead;
    DriverObject->MajorFunction[IRP_MJ_DEVICE_CONTROL] = KbfiltrDeviceControl;

    DriverObject->DriverUnload              = KbfiltrUnload;
    DriverObject->DriverExtension->AddDevice = KbfiltrAddDevice;

    /* Create the control device. */
    status = IoCreateDevice(
        DriverObject,
        sizeof(CTRL_EXT),
        (PUNICODE_STRING)&gDeviceName,
        FILE_DEVICE_KEYBOARD,
        FILE_DEVICE_SECURE_OPEN,
        FALSE,
        &gCtrlDevice);

    if (!NT_SUCCESS(status)) return status;

    ctrlExt = (PCTRL_EXT)gCtrlDevice->DeviceExtension;
    RtlZeroMemory(ctrlExt, sizeof(CTRL_EXT));

    KeInitializeSpinLock(&ctrlExt->MacroLock);
    KeInitializeSpinLock(&ctrlExt->CsqLock);
    InitializeListHead(&ctrlExt->CsqList);

    status = IoCsqInitialize(
        &ctrlExt->Csq,
        CsqInsertIrp,
        CsqRemoveIrp,
        CsqPeekNextIrp,
        CsqAcquireLock,
        CsqReleaseLock,
        CsqCompleteCancelledIrp);

    if (!NT_SUCCESS(status)) {
        IoDeleteDevice(gCtrlDevice);
        gCtrlDevice = NULL;
        return status;
    }

    gCtrlDevice->Flags |=  DO_BUFFERED_IO;
    gCtrlDevice->Flags &= ~DO_DEVICE_INITIALIZING;

    status = IoCreateSymbolicLink(
        (PUNICODE_STRING)&gSymlinkName,
        (PUNICODE_STRING)&gDeviceName);

    if (!NT_SUCCESS(status)) {
        IoDeleteDevice(gCtrlDevice);
        gCtrlDevice = NULL;
    }

    return status;
}

/* ── DriverUnload ───────────────────────────────────────────────────────────── */

VOID KbfiltrUnload(PDRIVER_OBJECT DriverObject)
{
    UNREFERENCED_PARAMETER(DriverObject);

    if (gCtrlDevice) {
        PCTRL_EXT ctrlExt = (PCTRL_EXT)gCtrlDevice->DeviceExtension;
        PIRP      irp;

        /* Drain and cancel all pending read IRPs. */
        while ((irp = IoCsqRemoveNextIrp(&ctrlExt->Csq, NULL)) != NULL) {
            irp->IoStatus.Status      = STATUS_DEVICE_REMOVED;
            irp->IoStatus.Information = 0;
            IoCompleteRequest(irp, IO_NO_INCREMENT);
        }

        IoDeleteSymbolicLink((PUNICODE_STRING)&gSymlinkName);
        IoDeleteDevice(gCtrlDevice);
        gCtrlDevice = NULL;
    }
}

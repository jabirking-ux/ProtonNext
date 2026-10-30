//go:build windows

// Minimal WinDivert bindings.
//
// The DLL is loaded lazily by name, so no cgo and no third-party module are
// required: the build stays reproducible offline and the helper degrades
// gracefully (a clear error instead of a crash) when the driver is absent.
package main

import (
	"fmt"
	"path/filepath"
	"sync"
	"unsafe"

	"golang.org/x/sys/windows"
)

// Layers.
const (
	layerNetwork = 0
	layerFlow    = 2
	layerSocket  = 3
)

// Events.
const (
	eventNetworkPacket = 0
	eventSocketBind    = 1
	eventSocketConnect = 2
	eventSocketListen  = 3
	eventSocketAccept  = 4
	eventSocketClose   = 5
)

// Open flags.
const (
	flagSniff     = 0x0001
	flagDrop      = 0x0002
	flagRecvOnly  = 0x0004
	flagSendOnly  = 0x0008
	flagNoInstall = 0x0010
)

// Address flag bits.
const (
	addrSniffed     = 1 << 0
	addrOutbound    = 1 << 1
	addrLoopback    = 1 << 2
	addrImpostor    = 1 << 3
	addrIPv6        = 1 << 4
	addrIPChecksum  = 1 << 5
	addrTCPChecksum = 1 << 6
	addrUDPChecksum = 1 << 7
)

const maxPacketSize = 0xFFFF

// address mirrors WINDIVERT_ADDRESS. The trailing union is kept as raw bytes
// and decoded through accessors, which avoids depending on Go's struct layout
// matching a C union.
type address struct {
	Timestamp int64
	Layer     uint8
	Event     uint8
	Flags     uint8
	Reserved1 uint8
	Reserved2 uint32
	Union     [64]byte
}

func (a *address) outbound() bool { return a.Flags&addrOutbound != 0 }
func (a *address) impostor() bool { return a.Flags&addrImpostor != 0 }
func (a *address) ipv6() bool     { return a.Flags&addrIPv6 != 0 }

func (a *address) setOutbound(outbound bool) {
	if outbound {
		a.Flags |= addrOutbound
	} else {
		a.Flags &^= addrOutbound
	}
}

func (a *address) setImpostor() { a.Flags |= addrImpostor }

// Network layer accessors.
func (a *address) ifIdx() uint32 { return *(*uint32)(unsafe.Pointer(&a.Union[0])) }
func (a *address) setIfIdx(index uint32) {
	*(*uint32)(unsafe.Pointer(&a.Union[0])) = index
}
func (a *address) setSubIfIdx(index uint32) {
	*(*uint32)(unsafe.Pointer(&a.Union[4])) = index
}

// Socket layer accessors.
func (a *address) processID() uint32 { return *(*uint32)(unsafe.Pointer(&a.Union[16])) }
func (a *address) localPort() uint16 { return *(*uint16)(unsafe.Pointer(&a.Union[52])) }
func (a *address) protocol() uint8   { return a.Union[56] }

type windivert struct {
	once sync.Once

	dll               *windows.LazyDLL
	open              *windows.LazyProc
	recv              *windows.LazyProc
	send              *windows.LazyProc
	shutdown          *windows.LazyProc
	close             *windows.LazyProc
	calcChecksums     *windows.LazyProc
	helperParsePacket *windows.LazyProc
	loadErr           error
}

var library windivert

// load resolves WinDivert.dll from the directory that holds this executable so
// the bundled copy is used rather than whatever happens to be on PATH.
func (w *windivert) load() error {
	w.once.Do(func() {
		name := "WinDivert.dll"
		if self, err := selfDirectory(); err == nil {
			candidate := filepath.Join(self, "WinDivert.dll")
			if fileExists(candidate) {
				name = candidate
			}
		}
		w.dll = windows.NewLazyDLL(name)
		if err := w.dll.Load(); err != nil {
			w.loadErr = fmt.Errorf("cannot load %s: %w", name, err)
			return
		}
		w.open = w.dll.NewProc("WinDivertOpen")
		w.recv = w.dll.NewProc("WinDivertRecv")
		w.send = w.dll.NewProc("WinDivertSend")
		w.shutdown = w.dll.NewProc("WinDivertShutdown")
		w.close = w.dll.NewProc("WinDivertClose")
		w.calcChecksums = w.dll.NewProc("WinDivertHelperCalcChecksums")
		w.helperParsePacket = w.dll.NewProc("WinDivertHelperParsePacket")
	})
	return w.loadErr
}

type handle struct {
	raw uintptr
}

func openHandle(filter string, layer int16, priority int16, flags uint64) (*handle, error) {
	if err := library.load(); err != nil {
		return nil, err
	}
	filterBytes, err := windows.BytePtrFromString(filter)
	if err != nil {
		return nil, err
	}
	raw, _, lastErr := library.open.Call(
		uintptr(unsafe.Pointer(filterBytes)),
		uintptr(layer),
		uintptr(priority),
		uintptr(flags),
	)
	if raw == uintptr(windows.InvalidHandle) {
		return nil, fmt.Errorf("WinDivertOpen(%q) failed: %w", filter, lastErr)
	}
	return &handle{raw: raw}, nil
}

func (h *handle) receive(packet []byte, addr *address) (int, error) {
	var received uint32
	var packetPointer uintptr
	var packetLength uintptr
	if len(packet) > 0 {
		packetPointer = uintptr(unsafe.Pointer(&packet[0]))
		packetLength = uintptr(len(packet))
	}
	ok, _, lastErr := library.recv.Call(
		h.raw,
		packetPointer,
		packetLength,
		uintptr(unsafe.Pointer(&received)),
		uintptr(unsafe.Pointer(addr)),
	)
	if ok == 0 {
		return 0, lastErr
	}
	return int(received), nil
}

func (h *handle) sendPacket(packet []byte, addr *address) error {
	if len(packet) == 0 {
		return nil
	}
	var sent uint32
	ok, _, lastErr := library.send.Call(
		h.raw,
		uintptr(unsafe.Pointer(&packet[0])),
		uintptr(len(packet)),
		uintptr(unsafe.Pointer(&sent)),
		uintptr(unsafe.Pointer(addr)),
	)
	if ok == 0 {
		return lastErr
	}
	return nil
}

func (h *handle) recalculateChecksums(packet []byte, addr *address) {
	if len(packet) == 0 {
		return
	}
	// flags = 0 asks WinDivert to recompute every checksum it understands,
	// which is what we need after rewriting an address.
	library.calcChecksums.Call(
		uintptr(unsafe.Pointer(&packet[0])),
		uintptr(len(packet)),
		uintptr(unsafe.Pointer(addr)),
		0,
	)
}

func (h *handle) shutdownAndClose() {
	if h == nil || h.raw == 0 {
		return
	}
	library.shutdown.Call(h.raw, 2 /* WINDIVERT_SHUTDOWN_BOTH */)
	library.close.Call(h.raw)
	h.raw = 0
}

func selfDirectory() (string, error) {
	buffer := make([]uint16, windows.MAX_PATH)
	for {
		size, err := windows.GetModuleFileName(0, &buffer[0], uint32(len(buffer)))
		if err != nil {
			return "", err
		}
		if int(size) < len(buffer) {
			return filepath.Dir(windows.UTF16ToString(buffer[:size])), nil
		}
		buffer = make([]uint16, len(buffer)*2)
	}
}

func processImagePath(pid uint32) string {
	const queryLimited = 0x1000
	process, err := windows.OpenProcess(queryLimited, false, pid)
	if err != nil {
		return ""
	}
	defer windows.CloseHandle(process)
	buffer := make([]uint16, windows.MAX_PATH)
	for {
		size := uint32(len(buffer))
		if err := windows.QueryFullProcessImageName(process, 0, &buffer[0], &size); err != nil {
			if err == windows.ERROR_INSUFFICIENT_BUFFER && len(buffer) < 1<<16 {
				buffer = make([]uint16, len(buffer)*2)
				continue
			}
			return ""
		}
		return windows.UTF16ToString(buffer[:size])
	}
}

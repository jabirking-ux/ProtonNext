//go:build windows

// pvpn-split: per-application split tunneling for Windows.
//
// Why a separate helper is needed
// -------------------------------
// Windows offers no user-mode way to bind a foreign process's socket to a
// different interface: the WFP bind/connect redirect layers are reachable only
// from a kernel callout driver. Blocking an application on the tunnel would
// merely break it rather than route it around the VPN.
//
// So this helper uses WinDivert. Two handles are opened:
//
//   - a SOCKET-layer handle, in sniffing mode, that reports bind/connect/close
//     events together with the owning process id. That is how a local port is
//     associated with an executable path.
//   - a NETWORK-layer handle that captures the packets belonging to those
//     ports, rewrites the source address to the other interface's address,
//     recomputes the checksums and reinjects the packet on that interface.
//     Replies are translated back, so the application's socket -- which is
//     still bound to the original address -- keeps matching them.
//
// In exclude mode the selected applications are moved from the tunnel address
// to the physical address; in include mode the opposite happens, because there
// the physical link carries the default route and only the selected
// applications belong in the tunnel.
//
// Reinjected packets carry the Impostor flag and the filters say "not
// impostor", so nothing can loop back into the helper.
package main

import (
	"flag"
	"fmt"
	"log"
	"net"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"sync"
	"syscall"
	"time"
)

const (
	modeExclude = "exclude"
	modeInclude = "include"

	flowIdleTimeout  = 10 * time.Minute
	flowSweepEvery   = 30 * time.Second
	processCacheSize = 4096
)

type options struct {
	mode        string
	tunnelIP    string
	tunnelIndex uint
	physicalIP  string
	physIndex   uint
	apps        string
	logPath     string
}

// appMatcher decides whether an executable is one the user selected.
// Both full paths and bare executable names are accepted, and everything is
// compared case-insensitively because Windows paths are case-insensitive.
type appMatcher struct {
	paths map[string]struct{}
	names map[string]struct{}
}

func newAppMatcher(list string) *appMatcher {
	matcher := &appMatcher{
		paths: make(map[string]struct{}),
		names: make(map[string]struct{}),
	}
	for _, raw := range strings.Split(list, ";") {
		entry := strings.TrimSpace(strings.Trim(raw, `"`))
		if entry == "" {
			continue
		}
		entry = strings.ToLower(strings.ReplaceAll(entry, "/", `\`))
		if strings.Contains(entry, `\`) {
			matcher.paths[filepath.Clean(entry)] = struct{}{}
			matcher.names[filepath.Base(entry)] = struct{}{}
			continue
		}
		if !strings.HasSuffix(entry, ".exe") {
			matcher.names[entry+".exe"] = struct{}{}
		}
		matcher.names[entry] = struct{}{}
	}
	return matcher
}

func (m *appMatcher) empty() bool {
	return len(m.paths) == 0 && len(m.names) == 0
}

func (m *appMatcher) matches(imagePath string) bool {
	if imagePath == "" {
		return false
	}
	lowered := strings.ToLower(imagePath)
	if _, ok := m.paths[filepath.Clean(lowered)]; ok {
		return true
	}
	_, ok := m.names[filepath.Base(lowered)]
	return ok
}

// flowKey identifies a local endpoint. Ports are unique per protocol for the
// lifetime of a socket, which is all the correlation the helper needs.
type flowKey struct {
	protocol uint8
	port     uint16
}

type flowTable struct {
	mutex sync.RWMutex
	flows map[flowKey]time.Time
}

func newFlowTable() *flowTable {
	return &flowTable{flows: make(map[flowKey]time.Time)}
}

func (t *flowTable) add(key flowKey) {
	t.mutex.Lock()
	t.flows[key] = time.Now()
	t.mutex.Unlock()
}

func (t *flowTable) remove(key flowKey) {
	t.mutex.Lock()
	delete(t.flows, key)
	t.mutex.Unlock()
}

func (t *flowTable) has(key flowKey) bool {
	t.mutex.RLock()
	seen, ok := t.flows[key]
	t.mutex.RUnlock()
	if !ok {
		return false
	}
	if time.Since(seen) > flowIdleTimeout {
		t.remove(key)
		return false
	}
	return true
}

func (t *flowTable) touch(key flowKey) {
	t.mutex.Lock()
	if _, ok := t.flows[key]; ok {
		t.flows[key] = time.Now()
	}
	t.mutex.Unlock()
}

func (t *flowTable) sweep() {
	cutoff := time.Now().Add(-flowIdleTimeout)
	t.mutex.Lock()
	for key, seen := range t.flows {
		if seen.Before(cutoff) {
			delete(t.flows, key)
		}
	}
	t.mutex.Unlock()
}

func (t *flowTable) size() int {
	t.mutex.RLock()
	defer t.mutex.RUnlock()
	return len(t.flows)
}

// processCache avoids one OpenProcess per packet burst.
type processCache struct {
	mutex   sync.Mutex
	entries map[uint32]bool
}

func newProcessCache() *processCache {
	return &processCache{entries: make(map[uint32]bool)}
}

func (c *processCache) selected(pid uint32, matcher *appMatcher) bool {
	c.mutex.Lock()
	if selected, ok := c.entries[pid]; ok {
		c.mutex.Unlock()
		return selected
	}
	c.mutex.Unlock()

	selected := matcher.matches(processImagePath(pid))

	c.mutex.Lock()
	if len(c.entries) > processCacheSize {
		c.entries = make(map[uint32]bool)
	}
	c.entries[pid] = selected
	c.mutex.Unlock()
	return selected
}

func (c *processCache) forget(pid uint32) {
	c.mutex.Lock()
	delete(c.entries, pid)
	c.mutex.Unlock()
}

// ---------------------------------------------------------------------------
// IPv4 packet helpers
// ---------------------------------------------------------------------------

func ipv4Header(packet []byte) (headerLength int, protocol uint8, ok bool) {
	if len(packet) < 20 || packet[0]>>4 != 4 {
		return 0, 0, false
	}
	headerLength = int(packet[0]&0x0F) * 4
	if headerLength < 20 || len(packet) < headerLength {
		return 0, 0, false
	}
	return headerLength, packet[9], true
}

func ipv4Ports(packet []byte, headerLength int, protocol uint8) (source, destination uint16, ok bool) {
	if protocol != 6 && protocol != 17 {
		return 0, 0, false
	}
	if len(packet) < headerLength+4 {
		return 0, 0, false
	}
	source = uint16(packet[headerLength])<<8 | uint16(packet[headerLength+1])
	destination = uint16(packet[headerLength+2])<<8 | uint16(packet[headerLength+3])
	return source, destination, true
}

func setIPv4Source(packet []byte, address net.IP) {
	copy(packet[12:16], address.To4())
}

func setIPv4Destination(packet []byte, address net.IP) {
	copy(packet[16:20], address.To4())
}

func ipv4SourceEquals(packet []byte, address net.IP) bool {
	return net.IP(packet[12:16]).Equal(address)
}

func ipv4DestinationEquals(packet []byte, address net.IP) bool {
	return net.IP(packet[16:20]).Equal(address)
}

// ---------------------------------------------------------------------------
// Helper core
// ---------------------------------------------------------------------------

type splitter struct {
	options options

	matcher   *appMatcher
	flows     *flowTable
	processes *processCache

	// fromAddress is the address the selected applications currently use, and
	// toAddress is where they should be moved. fromIndex/toIndex are the
	// matching interface indices used when reinjecting.
	fromAddress net.IP
	toAddress   net.IP
	toIndex     uint32
	fromIndex   uint32

	networkHandle *handle
	socketHandle  *handle
}

func (s *splitter) networkFilter() string {
	// Outbound packets still carrying the old source address, plus the replies
	// addressed to the new one. Everything else never reaches the helper.
	return fmt.Sprintf(
		"not impostor and not loopback and ip and "+
			"((outbound and ip.SrcAddr == %s) or (inbound and ip.DstAddr == %s))",
		s.fromAddress.String(), s.toAddress.String(),
	)
}

func (s *splitter) socketFilter() string {
	return "event = CONNECT or event = BIND or event = CLOSE"
}

// watchSockets keeps the flow table in sync with the sockets owned by the
// selected applications.
func (s *splitter) watchSockets(stop <-chan struct{}) {
	var addr address
	for {
		select {
		case <-stop:
			return
		default:
		}
		if _, err := s.socketHandle.receive(nil, &addr); err != nil {
			if isShutdown(err) {
				return
			}
			log.Printf("socket layer receive failed: %v", err)
			time.Sleep(200 * time.Millisecond)
			continue
		}
		pid := addr.processID()
		key := flowKey{protocol: addr.protocol(), port: addr.localPort()}
		if key.port == 0 {
			continue
		}
		switch addr.Event {
		case eventSocketBind, eventSocketConnect, eventSocketListen, eventSocketAccept:
			if s.processes.selected(pid, s.matcher) {
				s.flows.add(key)
			}
		case eventSocketClose:
			s.flows.remove(key)
			s.processes.forget(pid)
		}
	}
}

// translate rewrites and reinjects one packet. It returns false when the packet
// is not ours, in which case it is reinjected untouched so the stack still sees
// it.
func (s *splitter) translate(packet []byte, addr *address) bool {
	headerLength, protocol, ok := ipv4Header(packet)
	if !ok {
		return false
	}
	sourcePort, destinationPort, ok := ipv4Ports(packet, headerLength, protocol)
	if !ok {
		return false
	}

	if addr.outbound() {
		if !ipv4SourceEquals(packet, s.fromAddress) {
			return false
		}
		key := flowKey{protocol: protocol, port: sourcePort}
		if !s.flows.has(key) {
			return false
		}
		s.flows.touch(key)
		setIPv4Source(packet, s.toAddress)
		addr.setIfIdx(s.toIndex)
		addr.setSubIfIdx(0)
		addr.setOutbound(true)
	} else {
		if !ipv4DestinationEquals(packet, s.toAddress) {
			return false
		}
		key := flowKey{protocol: protocol, port: destinationPort}
		if !s.flows.has(key) {
			return false
		}
		s.flows.touch(key)
		setIPv4Destination(packet, s.fromAddress)
		// The reply has to appear on the interface the socket believes it is
		// using, otherwise the stack drops it as a martian.
		addr.setIfIdx(s.fromIndex)
		addr.setSubIfIdx(0)
		addr.setOutbound(false)
	}

	addr.setImpostor()
	s.networkHandle.recalculateChecksums(packet, addr)
	return true
}

func (s *splitter) pumpNetwork(stop <-chan struct{}) {
	packet := make([]byte, maxPacketSize)
	var addr address
	for {
		select {
		case <-stop:
			return
		default:
		}
		length, err := s.networkHandle.receive(packet, &addr)
		if err != nil {
			if isShutdown(err) {
				return
			}
			log.Printf("network layer receive failed: %v", err)
			time.Sleep(200 * time.Millisecond)
			continue
		}
		current := packet[:length]
		s.translate(current, &addr)
		// Whether or not it was translated the packet must be reinjected, or the
		// connection simply stalls.
		if err := s.networkHandle.sendPacket(current, &addr); err != nil {
			log.Printf("reinjection failed: %v", err)
		}
	}
}

func isShutdown(err error) bool {
	if err == nil {
		return false
	}
	if errno, ok := err.(syscall.Errno); ok {
		// ERROR_NO_DATA is what Recv returns once the handle is shut down.
		return errno == syscall.Errno(232) || errno == syscall.Errno(6)
	}
	return false
}

func (s *splitter) run() error {
	var err error
	s.socketHandle, err = openHandle(s.socketFilter(), layerSocket, 0, flagSniff|flagRecvOnly)
	if err != nil {
		return fmt.Errorf("cannot watch socket events: %w", err)
	}
	defer s.socketHandle.shutdownAndClose()

	s.networkHandle, err = openHandle(s.networkFilter(), layerNetwork, 0, 0)
	if err != nil {
		return fmt.Errorf("cannot capture packets: %w", err)
	}
	defer s.networkHandle.shutdownAndClose()

	stop := make(chan struct{})
	signals := make(chan os.Signal, 1)
	signal.Notify(signals, os.Interrupt, syscall.SIGTERM)

	var waitGroup sync.WaitGroup
	waitGroup.Add(2)
	go func() { defer waitGroup.Done(); s.watchSockets(stop) }()
	go func() { defer waitGroup.Done(); s.pumpNetwork(stop) }()

	ticker := time.NewTicker(flowSweepEvery)
	defer ticker.Stop()

	log.Printf(
		"running: mode=%s moving %s (if %d) -> %s (if %d)",
		s.options.mode, s.fromAddress, s.fromIndex, s.toAddress, s.toIndex,
	)

	for {
		select {
		case <-signals:
			log.Printf("stopping on signal")
			close(stop)
			s.socketHandle.shutdownAndClose()
			s.networkHandle.shutdownAndClose()
			waitGroup.Wait()
			return nil
		case <-ticker.C:
			s.flows.sweep()
		}
	}
}

func main() {
	var opts options
	flag.StringVar(&opts.mode, "mode", modeExclude, "exclude or include")
	flag.StringVar(&opts.tunnelIP, "tun-ip", "", "IPv4 address of the tunnel adapter")
	flag.UintVar(&opts.tunnelIndex, "tun-if", 0, "interface index of the tunnel adapter")
	flag.StringVar(&opts.physicalIP, "phys-ip", "", "IPv4 address of the physical adapter")
	flag.UintVar(&opts.physIndex, "phys-if", 0, "interface index of the physical adapter")
	flag.StringVar(&opts.apps, "apps", "", "semicolon separated executables or paths")
	flag.StringVar(&opts.logPath, "log", "", "log file path")
	flag.Parse()

	if opts.logPath != "" {
		if file, err := os.OpenFile(opts.logPath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o600); err == nil {
			defer file.Close()
			log.SetOutput(file)
		}
	}
	log.SetFlags(log.LstdFlags)

	tunnelIP := net.ParseIP(opts.tunnelIP)
	physicalIP := net.ParseIP(opts.physicalIP)
	if tunnelIP == nil || tunnelIP.To4() == nil {
		log.Fatalf("invalid -tun-ip %q", opts.tunnelIP)
	}
	if physicalIP == nil || physicalIP.To4() == nil {
		log.Fatalf("invalid -phys-ip %q", opts.physicalIP)
	}
	if opts.tunnelIndex == 0 || opts.physIndex == 0 {
		log.Fatalf("both -tun-if and -phys-if are required")
	}

	matcher := newAppMatcher(opts.apps)
	if matcher.empty() {
		log.Fatalf("no applications were given; nothing to do")
	}

	instance := &splitter{
		options:   opts,
		matcher:   matcher,
		flows:     newFlowTable(),
		processes: newProcessCache(),
	}

	switch strings.ToLower(opts.mode) {
	case modeInclude:
		// Only the selected applications belong in the tunnel.
		instance.fromAddress = physicalIP
		instance.fromIndex = uint32(opts.physIndex)
		instance.toAddress = tunnelIP
		instance.toIndex = uint32(opts.tunnelIndex)
	default:
		// The selected applications must bypass the tunnel.
		instance.fromAddress = tunnelIP
		instance.fromIndex = uint32(opts.tunnelIndex)
		instance.toAddress = physicalIP
		instance.toIndex = uint32(opts.physIndex)
	}

	if err := instance.run(); err != nil {
		log.Fatalf("%v", err)
	}
	log.Printf("stopped after handling %d tracked flows", instance.flows.size())
}

func fileExists(path string) bool {
	info, err := os.Stat(path)
	return err == nil && !info.IsDir()
}

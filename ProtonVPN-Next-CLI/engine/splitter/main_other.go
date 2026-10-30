//go:build !windows

// The helper only exists on Windows: on Linux the same job is done in the
// kernel with cgroup v2, nftables and policy routing, which needs no helper
// process. This stub keeps "go build ./..." and "go vet ./..." working on Linux
// build hosts.
package main

import (
	"fmt"
	"os"
)

func main() {
	fmt.Fprintln(os.Stderr, "pvpn-split is a Windows-only helper; Linux uses cgroup v2 and policy routing instead")
	os.Exit(1)
}

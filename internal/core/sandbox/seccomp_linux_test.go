//go:build linux

package sandbox

import "testing"

func TestDefaultAgentSyscallsIncludeNodeRuntimePrimitives(t *testing.T) {
	allowed := make(map[string]struct{})
	for _, name := range defaultAgentSyscalls() {
		allowed[name] = struct{}{}
	}

	// Modern Node/libuv needs clone3 for worker creation, epoll_pwait for its
	// event loop, and madvise while initializing V8. Returning EPERM for these
	// calls causes native assertions or a segmentation fault before user code.
	for _, name := range []string{"clone3", "epoll_pwait", "madvise"} {
		if _, ok := allowed[name]; !ok {
			t.Errorf("default agent syscall allowlist is missing %q", name)
		}
		if _, ok := syscallNumber(name); !ok {
			t.Errorf("syscall table is missing %q", name)
		}
	}
}
